"""Nginx Unit Certbot plugins.

Authenticate and Install new o renewed certificates on Nginx Unit
Authenticator is built on Certbot Webroot giant shoulders

"""
import collections
import copy
import json
import logging
from datetime import datetime

from typing import Any, Callable, Optional, List, Union, Iterable, DefaultDict, Set, Type

from acme import challenges
from certbot import errors
from certbot import interfaces
from certbot.achallenges import AnnotatedChallenge
from certbot.compat import filesystem
from certbot.compat import os
from certbot.display import util as display_util
from certbot.plugins import common
from certbot.plugins.util import get_prefixes
from certbot.util import safe_open

from .unitc import Unitc

CONFIG_TLS_CERTIFICATE_PATH = "/listeners/*:443/tls/certificate"

logger = logging.getLogger(__name__)


class Configurator(common.Installer, interfaces.Authenticator):
    """Nginx Unit certificate authenticator and installer plugin for Certbot"""

    description = """\
    Nginx Unit certificate installer plugin for Certbot: \
    saves the necessary validation files to a .well-known/acme-challenge/ directory within the \
    nominated webroot path. Nginx Unit server must be running. \
    HTTP challenge only (wildcards not supported)."""

    MORE_INFO = """\
    Authenticator plugin that performs http-01 challenge by saving
    necessary validation resources to appropriate paths on the file
    system. It expects that there is some other HTTP server configured
    to serve all files under specified web root ({0})."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._prepared = False
        self._configuration = None
        self.unitc = Unitc()
        self._entropy = datetime.now().strftime("%Y%m%d%H%M%S")

        self._challenge_path: str = ""
        self._full_root: str = ""
        self._performed: DefaultDict[str, Set[AnnotatedChallenge]] = collections.defaultdict(set)
        self._created_dirs: List[str] = []
        self._to_remove: List[str] = []
        self._backup_routes: List[str] = []

    def get_all_names(self) -> Iterable[str]:
        return []

    def deploy_cert(self, domain: str, cert_path: str, key_path: str, chain_path: str, fullchain_path: str) -> None:
        """Deploy certificate.

        :param str domain: domain to deploy certificate file
        :param str cert_path: absolute path to the certificate file
        :param str key_path: absolute path to the private key file
        :param str chain_path: absolute path to the certificate chain file
        :param str fullchain_path: absolute path to the certificate fullchain
            file (cert plus chain)

        :raises .PluginError: when cert cannot be deployed

        """
        logger.debug("deploy cert for domain: %s", domain)

        cert_bundle_name = domain + "_" + self._entropy
        self._upload_certificates(fullchain_path, key_path, cert_bundle_name)

        certificates_chains = self._get_unit_configuration("/certificates")

        old_certificate_bundle_names = []
        for bundle_name, certificate in certificates_chains.items():
            for chain in certificate["chain"]:
                # @todo check validity chain["validity"]["until"]?
                if bundle_name == cert_bundle_name or chain["subject"]["common_name"] != domain:
                    continue
                old_certificate_bundle_names.append(bundle_name)

        if self._configuration is None:
            self._configuration = self._get_unit_configuration("/config")
        self._update_certificate_name_list_to_config(cert_bundle_name, old_certificate_bundle_names)

        display_util.notify(f"Remove old certificates for {domain}")
        for old_bundle_name in old_certificate_bundle_names:
            self._delete_certificates(old_bundle_name)

    def _upload_certificates(self, fullchain_path: str, key_path: str, cert_bundle_name: str):
        certificates = self._get_certificates_content(fullchain_path, key_path)
        path = "/certificates/" + cert_bundle_name
        success_message = "Certificate deployed"
        error_message = "nginx unit copy to /certificates failed"
        self.unitc.put(path, certificates, success_message, error_message)

    def _delete_certificates(self, cert_bundle_name: str):
        path = "/certificates/" + cert_bundle_name
        success_message = "Certificate deleted"
        error_message = "nginx unit delete from /certificates failed"
        self.unitc.delete(path, None, success_message, error_message)

    def _update_certificate_name_list_to_config(self, cert_bundle_name: str, bundle_names_to_remove):
        self._ensure_tls_listener()

        cert_bundle_names = self._configuration["listeners"]["*:443"]["tls"]["certificate"]
        cert_bundle_names = [item for item in cert_bundle_names if item not in bundle_names_to_remove]
        cert_bundle_names.append(cert_bundle_name)
        self._configuration["listeners"]["*:443"]["tls"]["certificate"] = cert_bundle_names

        path = "/config/listeners"
        input_data = json.dumps(self._configuration["listeners"]).encode()
        success_message = "Certificate deployed"
        error_message = "nginx unit copy to /certificates failed"

        self.unitc.put(path, input_data, success_message, error_message)

    def _ensure_tls_listener(self):
        if "listeners" not in self._configuration:
            raise errors.PluginError("No listeners configured")
        if "*:443" not in self._configuration["listeners"]:
            if "*:80" not in self._configuration["listeners"]:
                raise errors.PluginError("No '*:80' default listeners configured")
            self._configuration["listeners"]["*:443"] = copy.deepcopy(self._configuration["listeners"]["*:80"])

        if "tls" not in self._configuration["listeners"]["*:443"]:
            self._configuration["listeners"]["*:443"]["tls"] = {}
        if "certificate" not in self._configuration["listeners"]["*:443"]["tls"]:
            self._configuration["listeners"]["*:443"]["tls"]["certificate"] = []

    def _ensure_challenge_listener(self):
        success_message = "Updated listener for acme challenge"
        error_message = "Update listener for acme challenge failed"

        if "listeners" not in self._configuration:
            raise errors.PluginError("No listeners configured")
        if "*:80" not in self._configuration["listeners"]:
            self._backup_routes = self._configuration.get("routes", [])
            default_route = self._ensure_acme_route("routes")
            self._configuration["listeners"]["*:80"] = {"pass": default_route}
            listener_route = "/config/listeners/*:80"
            listener80 = json.dumps(self._configuration["listeners"]["*:80"]).encode()
            self.unitc.put(listener_route, listener80, success_message, error_message)
            self._to_remove.append("/config/listeners/*:80")
            return
        if "pass" not in self._configuration["listeners"]["*:80"]:
            raise errors.PluginError("Cannot configure the route for the *:80 listener")

        actual_route = self._configuration["listeners"]["*:80"]["pass"]
        self._backup_routes = self._configuration.get("routes", [])
        default_route = self._ensure_acme_route(actual_route)
        if actual_route == default_route:
            return

        self._configuration["listeners"]["*:80"]["pass"] = default_route
        listener_route = "/config/listeners/*:80/pass"
        self.unitc.put(listener_route, json.dumps(default_route).encode(), success_message, error_message)

    def _ensure_acme_route(self, actual_route: str) -> str:
        acme_challenge_url = "/" + challenges.HTTP01.URI_ROOT_PATH + "/*"
        acme_route = [
            {
                "match": {"uri": acme_challenge_url},
                "action": {"share": self._challenge_path + "/$uri"},
            }
        ]
        if actual_route != "routes" and actual_route != "routes/acme":
            acme_route.append({"action": {"pass": actual_route}})

        acme_route_json = json.dumps(acme_route)

        if "routes" not in self._configuration or not self._configuration["routes"]:
            self._configuration["routes"] = acme_route
            self.unitc.put("/config/routes", acme_route_json.encode())
            return "routes"

        if isinstance(self._configuration["routes"], dict):
            if "acme" in self._configuration["routes"]:
                return "routes/acme"

            self._configuration["routes"]["acme"] = acme_route
            self.unitc.put("/config/routes/acme", acme_route_json.encode())
            return "routes/acme"

        if not isinstance(self._configuration["routes"], list):
            raise errors.PluginError("Cannot configure the routes: unknown route type")

        if not isinstance(self._configuration["routes"][0], dict):
            raise errors.PluginError("Cannot configure the routes: unknown route[0] type")

        first_route = self._configuration["routes"][0]
        if ("match" in first_route and "uri" in first_route["match"]
                and first_route["match"]["uri"] == acme_challenge_url):
            return "routes"

        routes = acme_route + self._configuration["routes"]
        self._configuration["routes"] = routes
        self.unitc.put("/config/routes", json.dumps(routes).encode())
        return "routes"

    @staticmethod
    def _get_certificates_content(fullchain_path, key_path):
        with open(key_path, "rb") as f:
            certificates = f.read()
        with open(fullchain_path, "rb") as f:
            certificates += f.read()
        return certificates

    def _get_unit_configuration(self, path: str):
        error_message = "nginx unit get configuration failed"
        configuration_str = self.unitc.get(path, "Get configuration", error_message)
        logger.debug("Conf str '%s'", configuration_str)

        # @todo wrap configuration to a dedicated class
        return json.loads(configuration_str)

    def enhance(self, domain: str, enhancement: str, options: Optional[Union[List[str], str]] = None) -> None:
        pass

    def supported_enhancements(self) -> List[str]:
        return []

    def save(self, title: Optional[str] = None, temporary: bool = False) -> None:
        pass

    def rollback_checkpoints(self, rollback: int = 1) -> None:
        pass

    def recovery_routine(self) -> None:
        pass

    def config_test(self) -> None:
        pass

    def restart(self) -> None:
        pass

    def prepare(self) -> None:
        """Prepare the authenticator/installer."""
        # @todo verify "unitc" executable
        # @todo lock to prevent concurrent multi update
        if self._prepared:
            return
        self._configuration = self._get_unit_configuration("/config")
        self._backup_routes = self._configuration.get("routes", [])
        self._prepared = True

    def more_info(self) -> str:  # pylint: disable=missing-function-docstring
        return self.MORE_INFO.format(self.conf("path"))

    ### Authenticator
    @classmethod
    def add_parser_arguments(cls, add: Callable[..., None]) -> None:
        add("path", default="/srv/www/unit/", type=str,
            help="public_html / webroot path. Only one catch 'em all temporary "
                 "directory --nginx-unit-path /srv/www/unit/ (default: /srv/www/unit/)")

    def get_chall_pref(self, domain: str) -> Iterable[Type[challenges.Challenge]]:
        # pylint: disable=unused-argument,missing-function-docstring
        return [challenges.HTTP01]

    def perform(self, achalls: List[AnnotatedChallenge]) -> List[challenges.ChallengeResponse]:

        self.prepare()
        self._set_webroot(achalls)
        self._create_challenge_dir()

        self._ensure_challenge_listener()

        return [self._perform_single(achall) for achall in achalls]

    def _set_webroot(self, achalls: Iterable[AnnotatedChallenge]) -> None:
        webroot_path = '/srv/www/unit/'
        if self.conf("path"):
            webroot_path = self.conf("path")

        logger.info("Using the webroot path %s for all domains.", webroot_path)

        if not os.path.isdir(webroot_path):
            raise errors.PluginError(
                "You should specify the webroot path (or temporary directory) '" +
                webroot_path + "' does not exist or is not a directory")

        self._challenge_path = os.path.abspath(webroot_path)

    def _create_challenge_dir(self) -> None:
        if not self._challenge_path:
            raise errors.PluginError(
                "Missing parts of nginx_unit plugin configuration.")

        self._full_root = os.path.join(self._challenge_path, os.path.normcase(challenges.HTTP01.URI_ROOT_PATH))
        logger.debug("Creating root challenges validation dir at %s", self._full_root)

        # Change the permissions to be writable (certbot GH #1389)
        # Umask is used instead of chmod to ensure the client can also
        # run as non-root (certbot GH #1795)
        old_umask = filesystem.umask(0o022)
        try:
            # We ignore the last prefix in the next iteration,
            # as it does not correspond to a folder path ('/' or 'C:')
            for prefix in sorted(get_prefixes(self._full_root)[:-1], key=len):
                if os.path.isdir(prefix):
                    # Don't try to create directory if it already exists, as some filesystems
                    # won't reliably raise EEXIST or EISDIR if directory exists.
                    continue
                try:
                    # Set owner as parent directory if possible, apply mode for Linux/Windows.
                    # For Linux, this is coupled with the "umask" call above because
                    # os.mkdir's "mode" parameter may not always work:
                    # https://docs.python.org/3/library/os.html#os.mkdir
                    filesystem.mkdir(prefix, 0o755)
                    self._created_dirs.append(prefix)
                    try:
                        filesystem.copy_ownership_and_apply_mode(
                            self._challenge_path, prefix, 0o755, copy_user=True, copy_group=True)
                    except (OSError, AttributeError) as exception:
                        logger.warning("Unable to change owner and uid of webroot directory")
                        logger.debug("Error was: %s", exception)
                except OSError as exception:
                    raise errors.PluginError(
                        "Couldn't create root for http-01 "
                        "challenge responses: {0}".format(exception))
        finally:
            filesystem.umask(old_umask)

    def _get_validation_path(self, root_path: str, achall: AnnotatedChallenge) -> str:
        return os.path.join(root_path, achall.chall.encode("token"))

    def _perform_single(self, achall: AnnotatedChallenge) -> challenges.ChallengeResponse:
        response, validation = achall.response_and_validation()

        root_path = self._full_root
        validation_path = self._get_validation_path(root_path, achall)
        logger.debug("Attempting to save validation to %s", validation_path)

        # Change permissions to be world-readable, owner-writable (certbot GH #1795)
        old_umask = filesystem.umask(0o022)
        try:
            with safe_open(validation_path, mode="wb", chmod=0o644) as validation_file:
                validation_file.write(validation.encode())
        finally:
            filesystem.umask(old_umask)

        self._performed[root_path].add(achall)
        return response

    def cleanup(self, achalls: List[AnnotatedChallenge]) -> None:  # pylint: disable=missing-function-docstring
        for config_path in self._to_remove:
            self.unitc.delete(config_path, None, "Delete tmp configuration failed")

        if self._configuration["routes"] != self._backup_routes:
            self.unitc.put("/config/routes", json.dumps(self._backup_routes).encode())

        for achall in achalls:
            root_path = self._full_root
            if root_path is not None:
                validation_path = self._get_validation_path(root_path, achall)
                logger.debug("Removing %s", validation_path)
                os.remove(validation_path)
                self._performed[root_path].remove(achall)

        not_removed: List[str] = []
        while self._created_dirs:
            path = self._created_dirs.pop()
            try:
                os.rmdir(path)
            except OSError as exc:
                not_removed.insert(0, path)
                logger.info("Challenge directory %s was not empty, didn't remove", path)
                logger.debug("Error was: %s", exc)
        self._created_dirs = not_removed
        logger.debug("All challenges cleaned up")
