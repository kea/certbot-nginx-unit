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
