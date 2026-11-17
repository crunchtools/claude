"""The host units in deploy/ say what the hosts need (#42).

Nothing here can run them, so what they must contain is pinned instead: a
unit that lost its rclone config or its seat list would install cleanly and
then push nothing, which only Nagios's "no marker" would ever show.
"""

from __future__ import annotations

import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def unit(path: Path) -> dict[str, dict[str, list[str]]]:
    """Sections of key -> every value, in order: systemd accumulates a
    repeated key such as Environment=, so the last one is not the answer."""
    sections: dict[str, dict[str, list[str]]] = {}
    current: dict[str, list[str]] = {}
    for line in path.read_text().replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
            continue
        key, _, value = line.partition("=")
        current.setdefault(key, []).append(value)
    return sections


class ExedoreUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = unit(DEPLOY / "exedore/skills-sync-push.service")["Service"]

    def test_it_reads_the_hosts_rclone_config(self) -> None:
        # root has no rclone config of its own on Exedore.
        self.assertIn("RCLONE_CONFIG=/etc/rclone.conf", self.service["Environment"])
        self.assertNotIn("User", self.service)

    def test_it_is_sandboxed(self) -> None:
        for key, value in {
            "NoNewPrivileges": "yes",
            "PrivateTmp": "yes",
            "ProtectSystem": "strict",
            "ProtectHome": "yes",
        }.items():
            self.assertEqual(self.service.get(key), [value], key)

    def test_it_pushes_every_max_seat_by_name(self) -> None:
        (exec_start,) = self.service["ExecStart"]
        words = exec_start.split()
        self.assertEqual(words[:2], ["/var/usrlocal/bin/skills-sync-push", "exedore"])
        self.assertEqual(
            words[2:],
            [f"max{n}=/srv/max{n}/data/josui-skills/.git/skills-sync.status" for n in range(1, 5)],
        )


class TimerTest(unittest.TestCase):
    def test_each_host_pushes_every_ten_minutes(self) -> None:
        for host in ("dolza", "exedore"):
            timer = unit(DEPLOY / f"{host}/skills-sync-push.timer")
            self.assertEqual(timer["Timer"]["OnUnitActiveSec"], ["10min"], host)
            self.assertEqual(timer["Install"]["WantedBy"], ["timers.target"], host)


if __name__ == "__main__":
    unittest.main()
