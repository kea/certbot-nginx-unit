"""Test for certbot_nginx.installer."""
import json
import tempfile

import pytest
from unittest.mock import patch

from certbot import errors
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


def only_80_listener_configuration_after_cert():
    return {
        "listeners": {
            "*:80": {"pass": "routes/acme"},
            "*:443": {"pass": "routes/default"}
        },
        "routes": {
            "acme": {
                "match": {"uri": "/.well-known/acme-challenge/*"},
                "action": {"share": "/srv/www/unit/$uri"},
            },
            "default": {
                "action": {"share": "/srv/www/unit/index.html"}
            }
        }
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
        return json.dumps(only_80_listener_configuration())

    return '{}'


@patch('certbot_nginx_unit.unitc')
def test_empty_configuration(unitc_mock):
    unitc_mock.get.side_effect = get_configuration_side_effect
    installer = Configurator([], [])
    installer.unitc = unitc_mock

    with tempfile.NamedTemporaryFile() as cert_file:
        assert [] == installer.get_all_names()
        with pytest.raises(errors.Error) as error_info:
            installer.deploy_cert("domain", "cert.pem", cert_file.name, "chain_path", cert_file.name)
        assert "No '*:80' default listeners configured" == str(error_info.value)


@patch('certbot_nginx_unit.unitc')
def test_only_80_listener_configuration(unitc_mock):
    unitc_mock.get.side_effect = get_configuration_side_effect_80_listener
    unitc_mock.put.side_effect = put_configuration_side_effect_80_listener
    installer = Configurator([], [])
    installer.unitc = unitc_mock

    notify = patch('certbot.display.util.notify')
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

    print(repr(unitc_mock.method_calls))
    unitc_mock.get.assert_any_call("/config", get_success_message, get_error_message)
    unitc_mock.get.assert_any_call('/certificates', get_success_message, get_error_message),
    unitc_mock.put.assert_any_call(
        '/routes',
         b'{"acme": [{"match": {"uri": "/.well-known/acme-challenge/*"}, "action": {"share": "/srv/www/unit/$uri"}}], "default": [{"action": {"share": "/srv/www/unit/index.html"}}]}'
    )
    unitc_mock.put.assert_any_call(
        '/config/listeners',
        b'{"*:80": {"pass": "routes/acme"}, "*:443": {"pass": "routes", "tls": {"certificate": ["domain_' + entropy.encode() + b'"]}}}',
        put_success_message,
        put_error_message
    )
    unitc_mock.put.assert_any_call(
        "/certificates/domain_" + entropy,
        b'certificate contentcertificate content',
        'Certificate deployed',
        'nginx unit copy to /certificates failed'
    )

    notify.stop()