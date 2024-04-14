from __future__ import annotations

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
        # @todo from json check if error
        if proc.returncode != 0 or '"error"' in output:
            raise errors.Error(error_message)
        else:
            display_util.notify(success_message)

        return output

    def get(self, path: str, success_message: str = "", error_message: str = "") -> str:
        return self.call("GET", path, None, success_message, error_message)

    def put(self, path: str, input_data: bytes | None = None, success_message: str = "", error_message: str = ""):
        self.call("PUT", path, input_data, success_message, error_message)

    def delete(self, path: str, input_data: bytes | None = None, success_message: str = "", error_message: str = ""):
        self.call("DELETE", path, input_data, success_message, error_message)
