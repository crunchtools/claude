"""seat-state, the managed hook that tells /agents whether a seat is busy and who drives it.

The events are shaped as Claude Code 2.1.304 sends them, captured from the real
binary: a typed prompt reaches UserPromptSubmit as `prompt`, a cross-session
message reaches it too (wrapped in <cross-session-message>), and /clear starts
the new conversation with SessionStart source=clear.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOTFS = Path(__file__).resolve().parent.parent / "rootfs"
SEAT_STATE = ROOTFS / "usr/libexec/developer/seat-state"
MANAGED = ROOTFS / "etc/claude-code/managed-settings.d/40-developer-seat.json"

FIRST = "4c3d8432-626e-4ab4-9b5d-6e5e958ce0be"
CLEARED = "7bbc1c5f-636e-473c-9820-c34794004e1c"
# As a real SendMessage reaches UserPromptSubmit: the wrapper, nothing before it.
PEER = (
    '<cross-session-message from="uds:/tmp/cc-socks/121.sock" from-name="Josui Prime" from-mode="bypass">\n'
    "[a99] do the thing\n</cross-session-message>"
)


class SeatStateTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.state = self.home / ".claude/seat-state.json"
        self.pin = self.home / ".config/josui/session-id"

    def hook(self, event: dict[str, str]) -> subprocess.CompletedProcess[str]:
        name = "prompt" if event["hook_event_name"] == "UserPromptSubmit" else "start"
        result = subprocess.run(
            [str(SEAT_STATE), name],
            input=json.dumps(event),
            env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=False,
        )
        # A hook must never block the prompt, and UserPromptSubmit's stdout
        # would be added to the conversation.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        return result

    def prompt(self, text: str, session: str = FIRST) -> subprocess.CompletedProcess[str]:
        return self.hook({"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": text})

    def start(self, source: str, session: str = CLEARED) -> subprocess.CompletedProcess[str]:
        return self.hook({"hook_event_name": "SessionStart", "session_id": session, "source": source})

    def seat(self) -> dict[str, str]:
        return json.loads(self.state.read_text())

    def test_a_typed_prompt_marks_the_seat_busy_and_manual(self) -> None:
        self.prompt("fix the flaky test in trentina")
        seat = self.seat()
        self.assertEqual(seat["state"], "busy")
        self.assertEqual(seat["owner"], "manual")
        self.assertEqual(seat["task"], "fix the flaky test in trentina")
        self.assertEqual(seat["session_id"], FIRST)
        self.assertRegex(seat["since"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")

    def test_the_task_is_cut_to_120_characters(self) -> None:
        self.prompt("x" * 300)
        self.assertEqual(self.seat()["task"], "x" * 120)

    def test_the_first_prompt_of_the_session_stays_the_task(self) -> None:
        self.prompt("first thing")
        since = self.seat()["since"]
        self.prompt("and another thing")
        self.assertEqual(self.seat()["task"], "first thing")
        self.assertEqual(self.seat()["since"], since)

    def test_a_new_session_takes_a_new_task(self) -> None:
        self.prompt("first thing")
        self.prompt("in a new conversation", session=CLEARED)
        self.assertEqual(self.seat()["task"], "in a new conversation")
        self.assertEqual(self.seat()["session_id"], CLEARED)

    def test_a_corrupt_state_file_is_reported_and_replaced(self) -> None:
        for broken in ("not json{", "[1, 2]"):
            self.state.parent.mkdir(parents=True, exist_ok=True)
            self.state.write_text(broken)
            result = self.prompt("first thing")
            self.assertIn("seat-state", result.stderr)
            self.assertEqual(self.seat()["task"], "first thing")

    def test_a_cross_session_message_is_not_a_person(self) -> None:
        self.prompt(PEER)
        self.assertFalse(self.state.exists())

    def test_a_typed_prompt_quoting_the_marker_is_still_a_person(self) -> None:
        self.prompt("why does the hook skip <cross-session-message from=x>? check it")
        self.assertEqual(self.seat()["owner"], "manual")
        self.assertEqual(self.seat()["state"], "busy")

    def test_a_typed_prompt_quoting_a_whole_peer_message_is_still_a_person(self) -> None:
        self.prompt("Josui sent this, what does it mean?\n" + PEER)
        self.assertEqual(self.seat()["owner"], "manual")

    def test_a_cross_session_message_leaves_a_manual_task_alone(self) -> None:
        self.prompt("first thing")
        before = self.state.read_text()
        self.prompt(PEER)
        self.assertEqual(self.state.read_text(), before)

    def test_clear_frees_the_seat(self) -> None:
        self.prompt("first thing")
        self.start("clear")
        seat = self.seat()
        self.assertEqual(seat["state"], "free")
        self.assertEqual(seat["session_id"], CLEARED)
        self.assertNotIn("task", seat)

    # developer-worker-claude resumes the pinned UUID: re-pinned to the cleared
    # conversation, a respawn does not bring the old one back.
    def test_clear_repins_the_session(self) -> None:
        self.pin.parent.mkdir(parents=True)
        self.pin.write_text(FIRST + "\n")
        self.start("clear")
        self.assertEqual(self.pin.read_text(), CLEARED + "\n")
        self.assertEqual(list(self.pin.parent.iterdir()), [self.pin])

    def test_clear_pins_even_with_no_pin_yet(self) -> None:
        self.start("clear")
        self.assertEqual(self.pin.read_text(), CLEARED + "\n")

    def test_other_session_starts_change_nothing(self) -> None:
        self.prompt("first thing")
        before = self.state.read_text()
        for source in ("startup", "resume", "compact"):
            self.start(source)
        self.assertEqual(self.state.read_text(), before)
        self.assertFalse(self.pin.exists())

    def test_a_session_id_that_is_not_a_uuid_is_not_pinned(self) -> None:
        self.start("clear", session="../../etc/passwd")
        self.assertFalse(self.pin.exists())

    def test_bad_input_is_reported_not_fatal(self) -> None:
        result = subprocess.run(
            [str(SEAT_STATE), "prompt"],
            input="not json",
            env={"HOME": str(self.home), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("seat-state", result.stderr)

    def test_an_unwritable_home_is_reported_not_fatal(self) -> None:
        (self.home / ".claude").write_text("not a directory\n")
        result = self.prompt("first thing")
        self.assertIn("seat-state", result.stderr)


class ManagedSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = json.loads(MANAGED.read_text())

    def test_autocompact_at_500k(self) -> None:
        self.assertEqual(self.settings["autoCompactWindow"], 500000)

    def test_hooks_run_seat_state_from_the_image(self) -> None:
        hooks = self.settings["hooks"]
        commands = {
            event: [h["command"] for group in hooks[event] for h in group["hooks"]]
            for event in ("UserPromptSubmit", "SessionStart")
        }
        self.assertEqual(commands["UserPromptSubmit"], ["/usr/libexec/developer/seat-state prompt"])
        self.assertEqual(commands["SessionStart"], ["/usr/libexec/developer/seat-state start"])
        self.assertTrue(SEAT_STATE.stat().st_mode & 0o111)
