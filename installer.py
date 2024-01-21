"""Nginx Unit Certbot plugins.

Install new o renewed certificates on Nginx Unit

"""
import json
import logging
from datetime import datetime

from typing import Callable, Optional, List, Union, Iterable

from certbot import interfaces
from certbot.plugins import common
from certbot.display import util as display_util

from typing import Any

from unitc import Unitc

CONFIG_TLS_CERTIFICATE_PATH = "/listeners/*:443/tls/certificate"

logger = logging.getLogger(__name__)


class Installer(common.Plugin, interfaces.Installer):
    """Nginx Unit plugin"""
    description = "Nginx Unit plugin"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._configuration = None
        self._prepared = None

    @classmethod
    def add_parser_arguments(cls, add: Callable[..., None]) -> None:
        pass

    def get_all_names(self) -> Iterable[str]:
        pass

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

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        cert_bundle_name = domain + "_" + now
        self._configuration = self._get_unit_configuration("/config")
        self._upload_certificates(fullchain_path, key_path, cert_bundle_name)

        certificates_chains = self._get_unit_configuration("/certificates")

        old_certificate_bundle_names = []
        for bundle_name, certificate in certificates_chains.items():
            for chain in certificate["chain"]:
                # @todo check validity chain["validity"]["until"]?
                if bundle_name == cert_bundle_name or chain["subject"]["common_name"] != domain:
                    continue
                old_certificate_bundle_names.append(bundle_name)

        self._update_certificate_name_list_to_config(cert_bundle_name, old_certificate_bundle_names)

        display_util.notify(f"Remove old certificates for {domain}")
        for old_bundle_name in old_certificate_bundle_names:
            self._delete_certificates(old_bundle_name)

    def _upload_certificates(self, fullchain_path: str, key_path: str, cert_bundle_name: str):
        certificates = self._get_certificates_content(fullchain_path, key_path)
        path = "/certificates/" + cert_bundle_name
        success_message = "Certificate deployed"
        error_messge = "nginx unit copy to /certificates failed"
        unitc = Unitc()
        unitc.put(path, certificates, success_message, error_messge)

    def _delete_certificates(self, cert_bundle_name: str):
        path = "/certificates/" + cert_bundle_name
        success_message = "Certificate deleted"
        error_message = "nginx unit delete from /certificates failed"
        unic = Unitc()
        unic.delete(path, None, success_message, error_message)

    def _update_certificate_name_list_to_config(self, cert_bundle_name: str, bundle_names_to_remove):

        if "listeners" not in self._configuration:
            self._configuration["listeners"] = {}
        if "*:443" not in self._configuration["listeners"]:
            self._configuration["listeners"]["*:443"] = {}
        if "tls" not in self._configuration["listeners"]["*:443"]:
            self._configuration["listeners"]["*:443"]["tls"] = {}
        if "certificate" not in self._configuration["listeners"]["*:443"]["tls"]:
            self._configuration["listeners"]["*:443"]["tls"]["certificate"] = []

        cert_bundle_names = self._configuration["listeners"]["*:443"]["tls"]["certificate"]
        cert_bundle_names = [item for item in cert_bundle_names if item not in bundle_names_to_remove]
        cert_bundle_names.append(cert_bundle_name)

        path = '/config' + CONFIG_TLS_CERTIFICATE_PATH
        input_data = json.dumps(cert_bundle_names).encode()
        success_message = "Certificate deployed"
        error_message = "nginx unit copy to /certificates failed"

        unitc = Unitc()
        unitc.put(path, input_data, success_message, error_message)
        self._configuration["listeners"]["*:443"]["tls"]["certificate"] = cert_bundle_names

    @staticmethod
    def _get_certificates_content(fullchain_path, key_path):
        with open(key_path, 'rb') as f:
            certificates = f.read()
        with open(fullchain_path, 'rb') as f:
            certificates += f.read()
        return certificates

    @staticmethod
    def _get_unit_configuration(path: str):
        error_message = "nginx unit get configuration failed"
        unitc = Unitc()
        configuration_str = unitc.get(path, None, "Get configuration", error_message)

        # wrap configuration to a dedicated class
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
        """Prepare the authenticator/installer.

        """
        # @todo verify "unitc" executable
        # @todo lock to prevent concurrent multi update
        self._prepared = True

        pass

    def more_info(self) -> str:
        pass
