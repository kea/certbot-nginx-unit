"""Test for certbot_nginx.installer."""
import json
import tempfile

from unittest import mock

from certbot import errors
from certbot.compat import os
from certbot.tests import util as test_util
from certbot_nginx_unit.configurator import Configurator


def empty_configuration():
    return {
        "listeners": {},
        "routes": [],
        "applications": {}
    }


def only_80_listener_configuration():
    return {
        "listeners": {
            "*:80": {
                "pass": "routes"
            }
        },
        "routes": [
            {
                "action": {
                    "share": "/srv/www/unit/index.html"
                }
            }
        ]
    }


def only_80_app_listener_configuration():
    return {
        "listeners": {
            "*:80": {
                "pass": "applications/dokuwiki"
            }
        },
        "routes": [],
        "application": {
            "dokuwiki": {
                "type": "php",
                "root": "/path/to/app/",
                "index": "doku.php"
            }
        }
    }


def only_80_listener_configuration_after_cert_list():
    return {
        "listeners": {
            "*:80": {"pass": "routes/acme"},
            "*:443": {"pass": "routes/default"}
        },
        "routes": [
            {
                "match": {"uri": "/.well-known/acme-challenge/*"},
                "action": {"share": "/srv/www/unit/$uri"},
            },
            {
                "action": {"share": "/srv/www/unit/index.html"}
            }
        ]
    }


def listener_443_string_certificate_configuration():
    return {
        "listeners": {
            "*:80": {"pass": "routes"},
            "*:443": {
                "pass": "routes",
                "tls": {"certificate": "existing_bundle"}
            }
        },
        "routes": []
    }


def renewal_configuration():
    return {
        "listeners": {
            "*:80": {"pass": "routes"},
            "*:443": {
                "pass": "routes",
                "tls": {"certificate": ["example_20200101000000"]}
            }
        },
        "routes": []
    }


def renewal_certificates_chains():
    # Common name differs from the lineage name ("example"), e.g. a SAN cert.
    return {
        "example_20200101000000": {
            "chain": [{"subject": {"common_name": "www.example.com"}}]
        }
    }


def get_configuration_side_effect_renewal(*args):
    if args[0] == "/config":
        return json.dumps(renewal_configuration())
    if args[0] == "/certificates":
        return json.dumps(renewal_certificates_chains())
    return 'invalid json'


def malformed_certificates_chains():
    # Mix a valid old bundle with malformed entries that lack the expected keys.
    return {
        "example_20200101000000": {
            "chain": [{"subject": {"common_name": "www.example.com"}}]
        },
        "no_chain_bundle": {},
        "bad_chain_entry": {"chain": ["not-a-dict"]},
        "not_even_a_dict": None
    }


def get_configuration_side_effect_malformed_certificates(*args):
    if args[0] == "/config":
        return json.dumps(renewal_configuration())
    if args[0] == "/certificates":
        return json.dumps(malformed_certificates_chains())
    return 'invalid json'


def dict_routes_configuration():
    return {
        "listeners": {
            "*:80": {"pass": "routes/main"}
        },
        "routes": {
            "main": [{"action": {"share": "/srv/www/unit/index.html"}}]
        }
    }


def get_configuration_side_effect_dict_routes(*args):
    if args[0] == "/config":
        return json.dumps(dict_routes_configuration())
    if args[0] == "/certificates":
        return '{}'
    return 'invalid json'


def get_configuration_side_effect(*args):
    if args[0] == "/config":
        return json.dumps(empty_configuration())
    if args[0] == "/certificates":
        return '{}'
    return 'invalid json'


def get_configuration_side_effect_80_listener(*args):
    if args[0] == "/config":
        return json.dumps(only_80_listener_configuration())
    if args[0] == "/certificates":
        return '{}'
    return 'invalid json'


def put_configuration_side_effect_80_listener(*args):
    if args[0] == "/config/listeners":
        return json.dumps(only_80_listener_configuration()['listeners'])

    return '{}'


def get_configuration_side_effect_443_string_certificate(*args):
    if args[0] == "/config":
        return json.dumps(listener_443_string_certificate_configuration())
    if args[0] == "/certificates":
        return '{}'
    return 'invalid json'


class ConfiguratorTest(test_util.ConfigTestCase):
    """Test for certbot_nginx.configutator"""

    def setUp(self):
        super().setUp()

        self.configuration = self.config
        self.config = None
        logs_dir = tempfile.mkdtemp('logs')
        self.config = self.get_nginx_unit_configurator(logs_dir)

    def get_nginx_unit_configurator(self, logs_dir):
        """Create a Configurator with the specified options."""

        backups = os.path.join(logs_dir, "backups")
        self.configuration.backup_dir = backups
        self.configuration.nginx_unit_path = logs_dir

        return Configurator(self.configuration, name="nginx_unit")

    @mock.patch('certbot_nginx_unit.unitc')
    def test_empty_configuration(self, unitc_mock):
        unitc_mock.get.side_effect = get_configuration_side_effect

        installer = self.config
        installer.unitc = unitc_mock
        installer.prepare()

        with tempfile.NamedTemporaryFile() as cert_file:
            assert [] == installer.get_all_names()
            with self.assertRaises(errors.PluginError) as ctx:
                installer.deploy_cert("domain", "cert.pem", cert_file.name, "chain_path", cert_file.name)

            expected_msg = "No '*:80' default listeners configured"
            self.assertEqual(str(ctx.exception), expected_msg)

    @mock.patch('certbot_nginx_unit.unitc')
    def test_only_80_listener_configuration(self, unitc_mock):
        unitc_mock.get.side_effect = get_configuration_side_effect_80_listener
        unitc_mock.put.side_effect = put_configuration_side_effect_80_listener

        installer = self.config
        installer.unitc = unitc_mock
        installer.prepare()

        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        with tempfile.NamedTemporaryFile() as cert_file:
            cert_file.write('certificate content'.encode())
            cert_file.seek(0)
            assert [] == installer.get_all_names()
            installer.deploy_cert("domain", "cert.pem", cert_file.name, "chain_path", cert_file.name)

        get_success_message = 'Get configuration'
        get_error_message = 'nginx unit get configuration failed'

        put_success_message = 'Certificate deployed'
        put_error_message = 'nginx unit copy to /certificates failed'

        entropy = installer._entropy

        unitc_mock.get.assert_any_call("/config", get_success_message, get_error_message)
        unitc_mock.get.assert_any_call('/certificates', get_success_message, get_error_message)
        unitc_mock.put.assert_any_call(
            "/certificates/domain_" + entropy,
            b'certificate contentcertificate content',
            'Certificate deployed',
            'nginx unit copy to /certificates failed'
        )

        unitc_mock.put.assert_any_call(
            '/config/listeners',
            b'{"*:80": {"pass": "routes"}, "*:443": {"pass": "routes", "tls": {"certificate": ["domain_' +
            entropy.encode() + b'"]}}}',
            put_success_message,
            put_error_message
        )

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    def test_deploy_cert_normalizes_string_certificate(self, unitc_mock):
        # Unit accepts tls.certificate as a single string; it must be normalized
        # to a list, otherwise the string would be iterated char by char.
        unitc_mock.get.side_effect = get_configuration_side_effect_443_string_certificate

        installer = self.config
        installer.unitc = unitc_mock
        installer.prepare()

        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        with tempfile.NamedTemporaryFile() as cert_file:
            cert_file.write('certificate content'.encode())
            cert_file.seek(0)
            installer.deploy_cert("domain", "cert.pem", cert_file.name, "chain_path", cert_file.name)

        certificate = installer._configuration["listeners"]["*:443"]["tls"]["certificate"]
        entropy = installer._entropy
        self.assertEqual(certificate, ["existing_bundle", "domain_" + entropy])

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    def test_deploy_cert_prunes_old_bundle_when_cn_differs_from_lineage(self, unitc_mock):
        # On renewal the lineage name ("example") may differ from the cert
        # common name ("www.example.com"). Old bundles must still be pruned,
        # matched by the "<domain>_" name prefix.
        unitc_mock.get.side_effect = get_configuration_side_effect_renewal

        installer = self.config
        installer.unitc = unitc_mock
        installer.prepare()

        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        with tempfile.NamedTemporaryFile() as cert_file:
            cert_file.write('certificate content'.encode())
            cert_file.seek(0)
            installer.deploy_cert("example", "cert.pem", cert_file.name, "chain_path", cert_file.name)

        entropy = installer._entropy

        # Old bundle removed from the listener, new one appended.
        certificate = installer._configuration["listeners"]["*:443"]["tls"]["certificate"]
        self.assertEqual(certificate, ["example_" + entropy])

        # Old bundle deleted from /certificates.
        unitc_mock.delete.assert_any_call(
            "/certificates/example_20200101000000",
            None,
            "Certificate deleted",
            "nginx unit delete from /certificates failed"
        )

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    def test_deploy_cert_survives_malformed_certificate_bundles(self, unitc_mock):
        # A malformed bundle in /certificates must not abort the renewal;
        # the valid old bundle is still pruned.
        unitc_mock.get.side_effect = get_configuration_side_effect_malformed_certificates

        installer = self.config
        installer.unitc = unitc_mock
        installer.prepare()

        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        with tempfile.NamedTemporaryFile() as cert_file:
            cert_file.write('certificate content'.encode())
            cert_file.seek(0)
            installer.deploy_cert("example", "cert.pem", cert_file.name, "chain_path", cert_file.name)

        entropy = installer._entropy

        certificate = installer._configuration["listeners"]["*:443"]["tls"]["certificate"]
        self.assertEqual(certificate, ["example_" + entropy])

        unitc_mock.delete.assert_any_call(
            "/certificates/example_20200101000000",
            None,
            "Certificate deleted",
            "nginx unit delete from /certificates failed"
        )

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    @mock.patch('certbot.achallenges.AnnotatedChallenge')
    def test_cleanup_restores_dict_routes(self, unitc_mock, challenge_mock):
        # With named (dict) routes, the acme route is injected in place. The
        # backup must be an independent copy so cleanup restores the original.
        unitc_mock.get.side_effect = get_configuration_side_effect_dict_routes

        challenge_mock.response_and_validation.return_value = ("response", "validation")
        challenge_mock.chall.encode.return_value = "token"

        configurator = self.config
        configurator.unitc = unitc_mock
        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        configurator.perform([challenge_mock])

        # acme route injected into the live config.
        self.assertIn("acme", configurator._configuration["routes"])
        # Backup stays pristine (no acme key), otherwise cleanup would skip restore.
        self.assertNotIn("acme", configurator._backup_routes)

        # The *:80 listener was repointed at the injected acme route.
        self.assertEqual(configurator._configuration["listeners"]["*:80"]["pass"], "routes/acme")
        self.assertEqual(configurator._backup_listener_pass, "routes/main")

        configurator.cleanup(challenge_mock)

        unitc_mock.put.assert_any_call(
            '/config/routes',
            json.dumps(dict_routes_configuration()['routes']).encode()
        )

        # The listener pass must be restored, otherwise it would dangle at the
        # deleted "routes/acme" route and corrupt the *:80 listener.
        unitc_mock.put.assert_any_call(
            '/config/listeners/*:80/pass',
            json.dumps("routes/main").encode()
        )
        self.assertEqual(configurator._configuration["listeners"]["*:80"]["pass"], "routes/main")
        self.assertIsNone(configurator._backup_listener_pass)

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    def test_cleanup_without_routes_key_does_not_raise(self, unitc_mock):
        # A Unit config may not contain a "routes" key at all (e.g. perform
        # aborted before any route was set). cleanup must not crash with a
        # KeyError while checking whether the routes need restoring.
        def side_effect(*args):
            if args[0] == "/config":
                return json.dumps({"listeners": {}})
            return 'invalid json'
        unitc_mock.get.side_effect = side_effect

        configurator = self.config
        configurator.unitc = unitc_mock
        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        configurator.prepare()
        self.assertNotIn("routes", configurator._configuration)

        # Empty achalls: exercise only the routes-restore branch of cleanup.
        configurator.cleanup([])

        # Backup is empty and the config has no routes: nothing to restore.
        for call in unitc_mock.put.call_args_list:
            self.assertNotEqual(call.args[0], "/config/routes")

        notify.stop()

    @mock.patch('certbot_nginx_unit.unitc')
    @mock.patch('certbot.achallenges.AnnotatedChallenge')
    def test_authenticate(self, unitc_mock, challenge_mock):
        unitc_mock.get.side_effect = get_configuration_side_effect_80_listener
        unitc_mock.put.side_effect = put_configuration_side_effect_80_listener

        challenge_mock.response_and_validation.return_value = ("response", "validation")
        challenge_mock.chall.encode.return_value = "token"

        webroot = self.configuration.nginx_unit_path.encode()
        configurator = self.config
        configurator.unitc = unitc_mock
        notify = mock.patch('certbot.display.util.notify')
        notify.start()

        assert ["response"] == configurator.perform([challenge_mock])

        get_success_message = 'Get configuration'
        get_error_message = 'nginx unit get configuration failed'

        unitc_mock.get.assert_any_call("/config", get_success_message, get_error_message)
        unitc_mock.put.assert_any_call(
            '/config/routes',
            b'[{"match": {"uri": "/.well-known/acme-challenge/*"}, "action": {"share": "' +
            webroot + b'/$uri"}}, {"action": {"share": "/srv/www/unit/index.html"}}]'
        )

        configurator.cleanup(challenge_mock)
        unitc_mock.put.assert_any_call(
            '/config/routes',
            json.dumps(only_80_listener_configuration()['routes']).encode()
        )

        notify.stop()
