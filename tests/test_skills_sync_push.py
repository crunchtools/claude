"""deploy/skills-sync-push, with a stand-in rclone (#42)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PUSH = Path(__file__).resolve().parent.parent / "deploy/skills-sync-push"
LINE = (
    "SKILLSSYNC written=1700000000 state=current head=abc123 origin=abc123 drift_since=0 fetched=1700000000\n"
)

# Records each `rcat <dest>` and the body it was given.
FAKE_RCLONE = """#!/bin/bash
[ "$1" = rcat ] || exit 9
dest=${2//\\//_}
case $dest in *"${FAIL_ON:-never}"*) cat > /dev/null; exit 5 ;; esac
cat > "$OUT/$dest"
"""


class PushTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.out = self.root / "out"
        self.out.mkdir()
        rclone = self.root / "rclone"
        rclone.write_text(FAKE_RCLONE)
        rclone.chmod(0o755)
        self.env = {"PATH": os.environ["PATH"], "RCLONE": str(rclone), "OUT": str(self.out)}

    def push(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PUSH), *args], env=self.env, capture_output=True, text=True, check=False, timeout=30
        )

    def status(self, name: str, text: str = LINE) -> Path:
        path = self.root / name
        path.write_text(text)
        return path

    def test_each_seat_goes_to_its_own_marker_with_host_and_seat(self) -> None:
        one, two = self.status("one"), self.status("two")
        result = self.push("exedore", f"max1={one}", f"max2={two}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.out / "pcloud:Monitoring_SkillsSync_exedore.max1").read_text(),
            "SKILLSSYNC host=exedore seat=max1 " + LINE.removeprefix("SKILLSSYNC "),
        )
        self.assertTrue((self.out / "pcloud:Monitoring_SkillsSync_exedore.max2").exists())

    def test_a_missing_or_bad_file_is_skipped_and_reported(self) -> None:
        good = self.status("good")
        bad = self.status("bad", "SKILLSSYNC state=current; rm -rf /\n")
        result = self.push("exedore", f"max1={self.root / 'gone'}", f"max2={bad}", f"max3={good}")
        self.assertEqual(result.returncode, 1)
        self.assertIn("max1: no status line", result.stderr)
        self.assertIn("max2: no status line", result.stderr)
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()), ["pcloud:Monitoring_SkillsSync_exedore.max3"]
        )

    def test_a_failed_upload_is_reported_and_the_rest_still_go(self) -> None:
        one, two = self.status("one"), self.status("two")
        self.env["FAIL_ON"] = "exedore.max1"
        result = self.push("exedore", f"max1={one}", f"max2={two}")
        self.assertEqual(result.returncode, 1)
        self.assertIn("max1: copying the status", result.stderr)
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()), ["pcloud:Monitoring_SkillsSync_exedore.max2"]
        )

    def test_names_are_checked(self) -> None:
        good = str(self.status("good"))
        for args in (["dolza"], ["Dolza", f"shared={good}"], ["dolza", f"../x={good}"], ["dolza", good]):
            self.assertEqual(self.push(*args).returncode, 2, args)
        self.assertEqual(list(self.out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
