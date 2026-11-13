"""Regression tests for the SecureChat store.  Run:  python3 -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.state import Store


def texts(snap, mine=None):
    return [m["text"] for m in snap["messages"] if mine is None or m["mine"] == mine]


class JoinTests(unittest.TestCase):
    def test_same_device_joining_twice_reuses_one_account(self):
        s = Store()
        a1 = s.add_user("An", "dev-1")
        a2 = s.add_user("An", "dev-1")          # double tap / Enter twice / rejoin
        self.assertEqual(a1["uid"], a2["uid"])
        self.assertEqual(len(s.users), 1)

    def test_rejoin_from_same_device_updates_name_and_keeps_key(self):
        s = Store()
        a = s.add_user("An", "dev-1")
        d = a["d"]
        a2 = s.add_user("An Nguyen", "dev-1")
        self.assertEqual(a2["name"], "An Nguyen")
        self.assertEqual(a2["d"], d)

    def test_two_students_with_the_same_name_are_told_apart(self):
        s = Store()
        s.add_user("An", "dev-1")
        b = s.add_user("an", "dev-2")
        self.assertEqual(b["name"], "an 2")

    def test_names_are_trimmed_and_limited(self):
        s = Store()
        self.assertEqual(s.add_user("   Minh    Anh  ", "d")["name"], "Minh Anh")
        self.assertEqual(s.add_user("", "e")["name"], "Anonymous")
        self.assertLessEqual(len(s.add_user("x" * 100, "f")["name"]), 24)


class MessagingTests(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.a = self.s.add_user("Alice", "A")
        self.b = self.s.add_user("Bob", "B")

    def test_message_is_delivered_once_and_verifies(self):
        self.s.send(self.a["token"], self.b["uid"], "hello")
        bob = self.s.student_snapshot(self.b["token"])
        self.assertEqual(texts(bob), ["hello"])
        self.assertTrue(bob["messages"][0]["valid"])
        self.assertEqual(texts(self.s.student_snapshot(self.a["token"]), mine=True), ["hello"])

    def test_cannot_message_yourself_or_send_empty(self):
        with self.assertRaises(ValueError):
            self.s.send(self.a["token"], self.a["uid"], "me")
        with self.assertRaises(ValueError):
            self.s.send(self.a["token"], self.b["uid"], "   ")

    def test_unknown_token_is_rejected(self):
        with self.assertRaises(ValueError):
            self.s.send("bad", self.b["uid"], "x")
        self.assertIsNone(self.s.student_snapshot("bad"))


class AttackTests(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.a = self.s.add_user("Alice", "A")
        self.b = self.s.add_user("Bob", "B")

    def bob(self):
        return self.s.student_snapshot(self.b["token"])

    def alice(self):
        return self.s.student_snapshot(self.a["token"])

    def test_held_message_is_invisible_to_recipient_until_released(self):
        self.s.set_hold(True)
        m = self.s.send(self.a["token"], self.b["uid"], "100k")
        self.assertEqual(texts(self.bob()), [])
        self.assertTrue(self.alice()["messages"][0]["pending"])
        self.s.attack(m["id"], "", "relay")
        self.assertEqual(texts(self.bob()), ["100k"])
        self.assertTrue(self.bob()["messages"][0]["valid"])

    def test_turning_hold_off_releases_stuck_messages(self):
        self.s.set_hold(True)
        self.s.send(self.a["token"], self.b["uid"], "queued")
        self.s.set_hold(False)
        self.assertEqual(texts(self.bob()), ["queued"])

    def test_tamper_held_message_is_detected_and_delivered_once(self):
        self.s.set_hold(True)
        m = self.s.send(self.a["token"], self.b["uid"], "100k")
        self.s.attack(m["id"], "9 trieu", "tamper")
        bob = self.bob()
        self.assertEqual(texts(bob), ["9 trieu"])
        self.assertFalse(bob["messages"][0]["valid"])
        # the sender still sees what they actually typed
        self.assertEqual(texts(self.alice(), mine=True), ["100k"])

    def test_forge_with_stolen_key_is_not_detected(self):
        self.s.set_hold(True)
        m = self.s.send(self.a["token"], self.b["uid"], "100k")
        self.s.attack(m["id"], "9 trieu", "forge")
        bob = self.bob()
        self.assertEqual(texts(bob), ["9 trieu"])
        self.assertTrue(bob["messages"][0]["valid"])

    def test_relay_of_delivered_message_is_refused(self):
        m = self.s.send(self.a["token"], self.b["uid"], "hi")
        with self.assertRaises(ValueError):
            self.s.attack(m["id"], "", "relay")
        self.assertEqual(texts(self.bob()), ["hi"])

    def test_injected_fake_message_is_hidden_from_the_real_sender(self):
        m = self.s.send(self.a["token"], self.b["uid"], "hi")
        self.s.attack(m["id"], "send me 9 trieu", "forge")
        self.assertEqual(texts(self.bob()), ["hi", "send me 9 trieu"])
        self.assertEqual(texts(self.alice(), mine=True), ["hi"])

    def test_tamper_on_delivered_message_fails_verification(self):
        m = self.s.send(self.a["token"], self.b["uid"], "hi")
        self.s.attack(m["id"], "bye", "tamper")
        self.assertEqual([x["valid"] for x in self.bob()["messages"]], [True, False])

    def test_attack_needs_new_text(self):
        m = self.s.send(self.a["token"], self.b["uid"], "hi")
        with self.assertRaises(ValueError):
            self.s.attack(m["id"], "  ", "forge")

    def test_reset_wipes_data_but_ids_and_events_keep_growing(self):
        before_event = self.s.event
        self.s.send(self.a["token"], self.b["uid"], "hi")
        self.s.reset()
        self.assertEqual(self.s.users, {})
        self.assertGreater(self.s.event, before_event)
        c = self.s.add_user("Carol", "C")
        self.assertGreater(c["uid"], self.b["uid"])


if __name__ == "__main__":
    unittest.main()
