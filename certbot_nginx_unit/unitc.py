from __future__ import annotations

import json
import tempfile
import subprocess
import logging
from certbot import errors
from certbot import util
from certbot.display import util as display_util

logger = logging.getLogger(__name__)


class Unitc(object):
    def call(self, method: str, path: str, input_data: bytes | None = None,
             success_message: str = "", error_message: str = "") -> str:
        output = ""
        with tempfile.TemporaryFile() as out:
            try:
                params = ["unitc", "--no-log", method, path]
                logger.debug("Unitc params: %s", " ".join(params))
                proc = subprocess.run(params,
                                      env=util.env_no_snap_for_external_calls(),
                                      input=input_data,
                                      stdout=out, stderr=out, check=False)
            except (OSError, ValueError):
                msg = "Unable to run the command: %s" + " ".join(params)
                logger.error(msg)
                raise errors.SubprocessError(msg)

            out.seek(0)
            output = out.read().decode("utf-8")
            logger.debug("Unitc result: %s", output)
        if proc.returncode != 0 or self._output_has_error(output):
            raise errors.Error(error_message)
        else:
            display_util.notify(success_message)

        return output

    @staticmethod
    def _output_has_error(output: str) -> bool:
        # Unit's control API signals failures with a top-level {"error": ...}
        # object. Match that structurally instead of scanning for the substring
        # '"error"', which false-positives on any config/response that merely
        # contains a route, header or value named "error". Non-JSON output is
        # not treated as an error here; hard failures surface via the exit code.
        try:
            parsed = json.loads(output)
        except (ValueError, TypeError):
            return False
        return isinstance(parsed, dict) and "error" in parsed

    def get(self, path: str, success_message: str = "", error_message: str = "") -> str:
        return self.call("GET", path, None, success_message, error_message)

    def put(self, path: str, input_data: bytes | None = None, success_message: str = "", error_message: str = ""):
        self.call("PUT", path, input_data, success_message, error_message)

    def delete(self, path: str, input_data: bytes | None = None, success_message: str = "", error_message: str = ""):
        self.call("DELETE", path, input_data, success_message, error_message)
