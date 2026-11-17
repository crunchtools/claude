"""The image says which release it is."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

CONTAINERFILE = Path(__file__).resolve().parent.parent / "Containerfile"


class LabelTest(unittest.TestCase):
    # The base image sets org.opencontainers.image.version to its own release
    # (podman 6.1.3), which the image inherited and reported as its version.
    def test_the_oci_version_label_is_this_release(self) -> None:
        labels = dict(re.findall(r'^LABEL ([\w.]+)="([^"]*)"', CONTAINERFILE.read_text(), re.M))
        self.assertRegex(labels["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(labels.get("org.opencontainers.image.version"), labels["version"])
