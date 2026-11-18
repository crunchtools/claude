"""The entrypoint refusing a token file it cannot read.

Its own file because it is skipped as root, which reads a file whatever its
mode. Gourmand matches an exception by path alone, so the exception for this
skip names this file and covers nothing else.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from test_entrypoint import EntrypointCase


class UnreadableTokenFileTest(EntrypointCase):
    @unittest.skipIf(os.geteuid() == 0, "root reads a file whatever its mode")
    def test_an_unreadable_token_file_stops_the_start(self) -> None:
        env = self.token_file("file-token\n")
        Path(env["TRENTINA_MCP_TOKEN_FILE"]).chmod(0)
        self.assert_refused(env)
