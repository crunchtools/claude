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


class AshigaruPinTest(unittest.TestCase):
    # The release asset can be replaced (rpm.yml uploads with --clobber), so
    # the build installs only an RPM whose hash is pinned here.
    def test_the_rpm_is_pinned_by_sha256(self) -> None:
        args = dict(re.findall(r"^ARG (ASHIGARU_\w+)=(\S*)$", CONTAINERFILE.read_text(), re.M))
        self.assertRegex(args["ASHIGARU_VERSION"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(args["ASHIGARU_SHA256"], r"^[0-9a-f]{64}$")
        self.assertIn("sha256sum -c --strict", CONTAINERFILE.read_text())


class AshigaruSkillTest(unittest.TestCase):
    # HOME is a volume, so the skill reaches Claude Code only through the
    # managed skills folder; the image build and container.yml check the link
    # resolves to the RPM's SKILL.md.
    def test_the_rpm_skill_is_linked_into_managed_skills(self) -> None:
        self.assertIn(
            "ln -s /usr/share/ashigaru/skills/ashigaru /etc/claude-code/.claude/skills/ashigaru",
            CONTAINERFILE.read_text(),
        )

    def test_the_build_checks_the_installed_version(self) -> None:
        self.assertIn(
            'rpm -q --qf \'%{VERSION}\' ashigaru)" = "$ASHIGARU_VERSION"', CONTAINERFILE.read_text()
        )

    def test_the_image_points_at_the_desk_but_carries_no_key(self) -> None:
        text = CONTAINERFILE.read_text()
        self.assertRegex(text, r"(?m)^\s+ASHIGARU_URL=https://ashigaru\.crunchtools\.com \\$")
        self.assertNotIn("ASHIGARU_API_KEY=", text)
