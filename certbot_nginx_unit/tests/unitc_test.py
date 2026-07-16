"""Tests for certbot_nginx_unit.unitc."""
import unittest

from unittest import mock

from certbot import errors
from certbot_nginx_unit.unitc import Unitc


class OutputHasErrorTest(unittest.TestCase):
    """Unit config output must be classified structurally, not by substring."""

    def test_top_level_error_object_is_error(self):
        self.assertTrue(Unitc._output_has_error('{"error": "Invalid configuration."}'))

    def test_error_substring_in_value_is_not_error(self):
        # A route/app/value that merely contains "error" must NOT be treated as
        # a failure. This is the regression the old substring check produced.
        output = '{"routes": [{"action": {"pass": "applications/error"}}]}'
        self.assertFalse(Unitc._output_has_error(output))

    def test_error_key_nested_deeper_is_not_error(self):
        output = '{"headers": {"X-Error": "boom"}}'
        self.assertFalse(Unitc._output_has_error(output))

    def test_success_object_is_not_error(self):
        self.assertFalse(Unitc._output_has_error('{"success": "Reconfiguration done."}'))

    def test_non_json_is_not_error(self):
        self.assertFalse(Unitc._output_has_error('not json at all'))

    def test_non_dict_json_is_not_error(self):
        self.assertFalse(Unitc._output_has_error('["error"]'))


class CallTest(unittest.TestCase):
    """End-to-end classification of the subprocess output by Unitc.call."""

    @staticmethod
    def _run_call(output_bytes, returncode):
        def subprocess_run(*args, **kwargs):
            kwargs["stdout"].write(output_bytes)
            return mock.Mock(returncode=returncode)

        with mock.patch("certbot_nginx_unit.unitc.subprocess.run", side_effect=subprocess_run), \
                mock.patch("certbot_nginx_unit.unitc.display_util.notify"):
            return Unitc().call("GET", "/config", None, "ok", "boom")

    def test_error_json_with_zero_exit_raises(self):
        # Unit reports config errors as {"error": ...} with a 0 exit code
        # (curl does not fail on HTTP 4xx); this must still be treated as error.
        with self.assertRaises(errors.Error) as ctx:
            self._run_call(b'{"error": "Invalid configuration."}', 0)
        self.assertEqual(str(ctx.exception), "boom")

    def test_benign_output_containing_error_substring_succeeds(self):
        output = b'{"routes": [{"action": {"pass": "applications/error"}}]}'
        result = self._run_call(output, 0)
        self.assertEqual(result, output.decode("utf-8"))

    def test_nonzero_exit_raises_even_on_non_json(self):
        with self.assertRaises(errors.Error):
            self._run_call(b'connection refused', 1)
