"""The image says which release it is."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINERFILE = ROOT / "Containerfile"


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


class ImageCopyTmpDirTest(unittest.TestCase):
    # The units cap /var/tmp at 1 GB of tmpfs, too small for a large
    # `podman build`; buildah stages under the storage volume instead.
    def test_buildah_stages_under_the_storage_volume(self) -> None:
        conf = ROOT / "rootfs/etc/containers/containers.conf.d/50-image-copy-tmp-dir.conf"
        self.assertRegex(conf.read_text(), r'(?ms)^\[engine\]$.*^image_copy_tmp_dir = "storage"$')


class GitTemplateTest(unittest.TestCase):
    # A crunchtools clone gets pre-commit's hooks without `pre-commit install`,
    # and no other clone does (a1124).
    def test_only_crunchtools_clones_get_pre_commit_hooks(self) -> None:
        text = (ROOT / "Containerfile").read_text()
        self.assertNotIn("init.templateDir", text)
        self.assertIn("'includeIf.hasconfig:remote.*.url:https://github.com/crunchtools/**.path'", text)
        include = (ROOT / "rootfs/usr/share/developer/crunchtools-hooks.gitconfig").read_text()
        self.assertRegex(include, r"(?m)^\thooksPath = /usr/share/developer/git-template/hooks$")
        hooks = "pre-commit init-templatedir -t pre-commit -t pre-merge-commit -t pre-push"
        self.assertRegex(text, re.escape(hooks) + r" \\\s+/usr/share/developer/git-template")

    def test_git_sets_the_hooks_path_only_for_a_crunchtools_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            system = Path(tmp) / "gitconfig"
            # The condition and the included file are the ones the image wires up.
            wiring = re.search(
                r"'includeIf\.(\S+)\.path' \\\s+/usr(/share/developer/\S+\.gitconfig)",
                CONTAINERFILE.read_text(),
            )
            if wiring is None:
                self.fail("the Containerfile does not wire the crunchtools hooks include")
            condition, include = wiring[1], ROOT / "rootfs/usr" / wiring[2].lstrip("/")
            system.write_text(f'[includeIf "{condition}"]\n\tpath = {include}\n')
            env = {
                "PATH": os.environ["PATH"],
                "GIT_CONFIG_SYSTEM": str(system),
                "GIT_CONFIG_GLOBAL": os.devnull,
            }

            def hooks_path(remote: str) -> str:
                repo = Path(tmp) / remote.replace("/", "_")
                subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
                subprocess.run(
                    ["git", "-C", str(repo), "remote", "add", "origin", remote], env=env, check=True
                )
                result = subprocess.run(
                    ["git", "-C", str(repo), "config", "core.hooksPath"],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip()

            self.assertEqual(
                hooks_path("https://github.com/crunchtools/developer"),
                "/usr/share/developer/git-template/hooks",
            )
            self.assertEqual(hooks_path("https://github.com/someone/else"), "")
