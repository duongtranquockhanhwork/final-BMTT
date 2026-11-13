"""
state.py - in-memory, thread-safe store for the classroom demo.

Everything lives in RAM and is wiped when the server stops or the teacher
presses Reset, so no student data is kept after the demonstration.

Actors:
  * students  - create an account by scanning a QR code and typing a name,
                then message each other. Every message is ECDSA-signed.
  * teacher   - the admin. Sees all accounts and messages, can reveal a
                private key (to play the attacker), and can tamper with or
                forge a message to show whether the recipient detects it.

Message model (one dict per message):
  orig_text / orig_r   what the sender actually typed and signed. The sender
                       always sees this version of their own message.
  text / sig_der / r   what is delivered to the recipient. Differs from the
                       original only if the teacher attacked the message.
  held                 waiting in the intercept queue (not delivered yet).
  injected             a NEW fake message created by the attacker in the
                       sender's name. Only the recipient (and the admin) see
                       it; the real sender never sent it.
"""

import os
import secrets
import threading
import time

from . import crypto

PALETTE = ["#2563eb", "#0f9d76", "#b4236b", "#d97706", "#7c3aed", "#0891b2",
           "#dc2626", "#4f46e5", "#15803d", "#be185d", "#c2410c", "#0d9488"]

MAX_NAME = 24
MAX_TEXT = 500


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        # A fixed passcode can be set (env SC_ADMIN_PASSCODE, or --passcode) so it
        # does not change on restart; otherwise a random 6-digit code is generated.
        self.admin_passcode = os.environ.get("SC_ADMIN_PASSCODE") or f"{secrets.randbelow(900000) + 100000}"
        # Several admin sessions can be valid at once (e.g. two tabs), so a login
        # never kicks out an earlier one. Tokens survive Reset so the teacher stays
        # logged in; they are gone only when the server stops.
        self.admin_tokens = set()
        self.base_url = "http://127.0.0.1:8070/"
        # Counters only ever grow (also across Reset) so ids and the polling
        # "event" number are never reused, which would confuse open browsers.
        self._uid = 0
        self._mid = 0
        self.event = 0
        self.reset()

    # ------------------------------------------------------------------ lifecycle
    def reset(self):
        with self.lock:
            self.users = {}          # uid -> dict (includes private key object)
            self.messages = []       # list of message dicts
            self.hold_mode = False   # intercept ("hold") mode for the live attack
            self._touch()

    def _touch(self):
        self.event += 1

    # ------------------------------------------------------------------ users
    def _unique_name(self, name, exclude_uid=None):
        """Return `name`, or `name 2`, `name 3`... so two students never look identical."""
        taken = {u["name"].casefold() for u in self.users.values() if u["uid"] != exclude_uid}
        if name.casefold() not in taken:
            return name
        n = 2
        while f"{name} {n}".casefold() in taken:
            n += 1
        return f"{name} {n}"

    def add_user(self, name, device_id=None):
        """Create an account, or return the existing one for the same device.

        `device_id` is a random id the browser keeps in localStorage. Joining twice
        from the same phone (double tap, pressing Enter while typing Vietnamese,
        pressing "Leave" and joining again) therefore reuses ONE account instead of
        creating duplicates; only the display name is updated.
        """
        name = " ".join((name or "").split())[:MAX_NAME] or "Anonymous"
        device_id = (str(device_id)[:64] if device_id else None)
        with self.lock:
            if device_id:
                for u in self.users.values():
                    if u["device_id"] == device_id:
                        if u["name"] != name:
                            u["name"] = self._unique_name(name, exclude_uid=u["uid"])
                            self._touch()
                        return u
            self._uid += 1
            uid = self._uid
            priv = crypto.generate_keypair()
            qx, qy = crypto.public_xy(priv)
            self.users[uid] = {
                "uid": uid, "name": self._unique_name(name), "color": PALETTE[(uid - 1) % len(PALETTE)],
                "priv": priv, "d": crypto.private_value(priv), "qx": qx, "qy": qy,
                "token": secrets.token_hex(12), "device_id": device_id, "created": time.time(),
            }
            self._touch()
            return self.users[uid]

    def user_by_token(self, token):
        if not token:
            return None
        with self.lock:
            for u in self.users.values():
                if u["token"] == token:
                    return u
        return None

    # ------------------------------------------------------------------ messaging
    def _new_message(self, from_uid, to_uid, text, sig_der, origin, attack_mode, held, injected=False):
        sender = self.users[from_uid]
        r, s = crypto.rs(sig_der)
        self._mid += 1
        msg = {
            "id": self._mid, "ts": time.time(),
            "from": from_uid, "to": to_uid,
            "orig_text": text, "orig_r": crypto.hx(r),          # what the sender signed
            "text": text, "sig_der": sig_der,                    # what is delivered
            "r": crypto.hx(r), "s": crypto.hx(s),
            "origin": origin,              # "user" | "attack"
            "attack_mode": attack_mode,    # None | "tamper" | "forge"
            "valid": crypto.verify(sender["priv"], text, sig_der),  # honest check result
            "held": held,                  # waiting in the intercept queue
            "injected": injected,          # fake new message, never sent by the real sender
        }
        self.messages.append(msg)
        self._touch()
        return msg

    def send(self, token, to_uid, text):
        with self.lock:
            sender = self.user_by_token(token)
            if not sender:
                raise ValueError("session expired")
            try:
                to_uid = int(to_uid)
            except (TypeError, ValueError):
                raise ValueError("unknown recipient")
            if to_uid not in self.users:
                raise ValueError("unknown recipient")
            if to_uid == sender["uid"]:
                raise ValueError("cannot message yourself")
            text = (text or "").strip()[:MAX_TEXT]
            if not text:
                raise ValueError("empty message")
            der = crypto.sign(sender["priv"], text)
            return self._new_message(sender["uid"], to_uid, text, der, "user", None, self.hold_mode)

    # ------------------------------------------------------------------ admin / attacker
    def _get(self, mid):
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            raise ValueError("message not found")
        m = next((m for m in self.messages if m["id"] == mid), None)
        if not m:
            raise ValueError("message not found")
        return m

    def _deliver_held(self, m, text, der, mode):
        sender = self.users[m["from"]]
        r, s = crypto.rs(der)
        m["text"], m["sig_der"] = text, der
        m["r"], m["s"] = crypto.hx(r), crypto.hx(s)
        m["valid"] = crypto.verify(sender["priv"], text, der)
        m["held"] = False
        m["origin"] = "user" if mode == "relay" else "attack"
        m["attack_mode"] = None if mode == "relay" else mode

    def set_hold(self, on):
        """Turn intercept mode on/off. Turning it off releases every held message
        unchanged, so no message is ever stuck in the queue."""
        with self.lock:
            self.hold_mode = bool(on)
            if not self.hold_mode:
                for m in self.messages:
                    if m["held"]:
                        self._deliver_held(m, m["text"], m["sig_der"], "relay")
            self._touch()

    def attack(self, base_mid, new_text, mode):
        """Act on a captured message.

        On a HELD message (intercept queue) the message is delivered exactly once:
          relay  : unchanged
          tamper : new text, ORIGINAL signature  -> recipient's check fails
          forge  : new text, RE-SIGNED with the sender's stolen private key
                   -> recipient's check passes (undetected)

        On an already DELIVERED message, tamper/forge send an extra fake message
        in the sender's name (the original stays as it was). Relay is not allowed
        there because it would only duplicate a message already delivered.
        """
        if mode not in ("relay", "tamper", "forge"):
            raise ValueError("unknown attack mode")
        with self.lock:
            base = self._get(base_mid)
            sender = self.users[base["from"]]
            new_text = (new_text or "").strip()[:MAX_TEXT]
            if mode != "relay" and not new_text:
                raise ValueError("enter the new (fake) content")

            if mode == "relay":
                if not base["held"]:
                    raise ValueError("this message was already delivered")
                text, der = base["text"], base["sig_der"]
            elif mode == "tamper":
                text, der = new_text, base["sig_der"]            # keep the sender's signature
            else:
                text, der = new_text, crypto.sign(sender["priv"], new_text)  # stolen key

            if base["held"]:
                self._deliver_held(base, text, der, mode)
                self._touch()
                return base
            return self._new_message(base["from"], base["to"], text, der, "attack", mode,
                                     held=False, injected=True)

    # ------------------------------------------------------------------ snapshots
    def _name(self, uid):
        u = self.users.get(uid)
        return u["name"] if u else "?"

    def student_snapshot(self, token):
        with self.lock:
            me = self.user_by_token(token)
            if not me:
                return None
            uid = me["uid"]
            contacts = [{"uid": u["uid"], "name": u["name"], "color": u["color"]}
                        for u in self.users.values() if u["uid"] != uid]
            msgs = []
            for m in self.messages:
                mine = m["from"] == uid
                if mine:
                    if m["injected"]:
                        continue          # the real sender never sent this fake message
                    msgs.append({"id": m["id"], "ts": m["ts"], "mine": True, "peer": m["to"],
                                 "text": m["orig_text"], "r": m["orig_r"][:16],
                                 "valid": None, "pending": m["held"]})
                elif m["to"] == uid:
                    if m["held"]:
                        continue          # not delivered yet
                    msgs.append({"id": m["id"], "ts": m["ts"], "mine": False, "peer": m["from"],
                                 "text": m["text"], "r": m["r"][:16],
                                 "valid": m["valid"], "pending": False})
            return {"me": {"uid": uid, "name": me["name"], "color": me["color"]},
                    "contacts": contacts, "messages": msgs, "event": self.event}

    def admin_snapshot(self):
        with self.lock:
            users = [{"uid": u["uid"], "name": u["name"], "color": u["color"],
                      "d": crypto.hx(u["d"]), "qx": crypto.hx(u["qx"])}
                     for u in self.users.values()]
            msgs = [{"id": m["id"], "ts": m["ts"], "from": m["from"], "to": m["to"],
                     "fromName": self._name(m["from"]), "toName": self._name(m["to"]),
                     "text": m["text"], "orig_text": m["orig_text"],
                     "r": m["r"][:16], "orig_r": m["orig_r"][:16],
                     "origin": m["origin"], "attack_mode": m["attack_mode"],
                     "valid": m["valid"], "held": m["held"], "injected": m["injected"]}
                    for m in self.messages]
            return {"users": users, "messages": msgs, "hold_mode": self.hold_mode,
                    "event": self.event}


STORE = Store()
