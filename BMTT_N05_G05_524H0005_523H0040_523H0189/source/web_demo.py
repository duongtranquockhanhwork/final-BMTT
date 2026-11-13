"""
web_demo.py - Interactive web GUI for the live demonstration.

Runs a small local web server (Python standard library only, no extra
dependency) and opens the demo page in the browser. Every button in the GUI
calls the SAME functions as the console demos (ecc_core.py, attack.py and the
`cryptography` library), so the GUI shows real results, not animations.

Run:  python web_demo.py            -> http://127.0.0.1:8000
      python web_demo.py --port 8080 --no-browser
"""

import hashlib
import io
import json
import secrets
import sys
import threading
import time
import unittest
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

import ecc_core as E
from attack import find_reused_nonce, recover_nonce, recover_private_key

HERE = Path(__file__).parent
WEB = HERE / "web"
PAGES = {"/": "index.html", "/index.html": "index.html", "/advanced": "advanced.html", "/advanced.html": "advanced.html"}
PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
LOCK = threading.Lock()


def hx(x: int) -> str:
    return f"{x:064x}"


def lib_verify(public_key, message: bytes, sig) -> bool:
    """Relying party: verification with the audited `cryptography` library."""
    try:
        public_key.verify(E.sig_to_der(sig), message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


# --------------------------------------------------------------------------- #
# Demo 1 - correct use (RSA-PSS and ECDSA P-256 with the audited library)
# --------------------------------------------------------------------------- #
class CorrectUse:
    def __init__(self):
        self.reset()

    def reset(self):
        self.rsa_key = self.ec_key = None
        self.rsa_imp = self.ec_imp = None
        self.signed_msg = self.rsa_sig = self.ec_sig = None

    def keygen(self, _):
        t = time.perf_counter()
        self.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.ec_key = ec.generate_private_key(ec.SECP256R1())
        self.rsa_imp = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.ec_imp = ec.generate_private_key(ec.SECP256R1())
        self.signed_msg = self.rsa_sig = self.ec_sig = None
        pn = self.ec_key.public_key().public_numbers()
        return {"rsa_n": f"{self.rsa_key.public_key().public_numbers().n:x}",
                "ec_d": hx(self.ec_key.private_numbers().private_value),
                "rsa_e": 65537, "rsa_bits": 2048,
                "ec_qx": hx(pn.x), "ec_qy": hx(pn.y),
                "ms": round((time.perf_counter() - t) * 1000)}

    def sign(self, req):
        if self.rsa_key is None:
            self.keygen(None)
        msg = req["message"].encode()
        self.signed_msg = msg
        self.rsa_sig = self.rsa_key.sign(msg, PSS, hashes.SHA256())
        self.ec_sig = self.ec_key.sign(msg, ec.ECDSA(hashes.SHA256()))
        return {"hash": hashlib.sha256(msg).hexdigest(),
                "rsa_sig": self.rsa_sig.hex(), "ec_sig": self.ec_sig.hex(),
                "rsa_len": len(self.rsa_sig), "ec_len": len(self.ec_sig)}

    def eve_sign(self, req):
        """Eve signs with HER OWN keys, pretending to be Alice; Bob checks with Alice's public key."""
        if self.rsa_key is None:
            raise ValueError("Generate the keys first.")
        msg = req["message"].encode()
        rsa_sig = self.rsa_imp.sign(msg, PSS, hashes.SHA256())
        ec_sig = self.ec_imp.sign(msg, ec.ECDSA(hashes.SHA256()))
        try:
            self.rsa_key.public_key().verify(rsa_sig, msg, PSS, hashes.SHA256())
            rsa_ok = True
        except InvalidSignature:
            rsa_ok = False
        try:
            self.ec_key.public_key().verify(ec_sig, msg, ec.ECDSA(hashes.SHA256()))
            ec_ok = True
        except InvalidSignature:
            ec_ok = False
        return {"rsa_ok": rsa_ok, "ec_ok": ec_ok, "rsa_sig": rsa_sig.hex(), "ec_sig": ec_sig.hex()}

    def verify(self, req):
        if self.signed_msg is None:
            raise ValueError("Sign a message first.")
        msg = req["message"].encode()
        impostor = bool(req.get("impostor"))
        rsa_pub = (self.rsa_imp if impostor else self.rsa_key).public_key()
        ec_pub = (self.ec_imp if impostor else self.ec_key).public_key()
        try:
            rsa_pub.verify(self.rsa_sig, msg, PSS, hashes.SHA256())
            rsa_ok = True
        except InvalidSignature:
            rsa_ok = False
        try:
            ec_pub.verify(self.ec_sig, msg, ec.ECDSA(hashes.SHA256()))
            ec_ok = True
        except InvalidSignature:
            ec_ok = False
        h_signed = hashlib.sha256(self.signed_msg).hexdigest()
        h_now = hashlib.sha256(msg).hexdigest()
        bits = bin(int(h_signed, 16) ^ int(h_now, 16)).count("1")
        return {"rsa_ok": rsa_ok, "ec_ok": ec_ok, "impostor": impostor,
                "hash_signed": h_signed, "hash_now": h_now, "bits_changed": bits,
                "modified": msg != self.signed_msg}


# --------------------------------------------------------------------------- #
# Demos 2 + 3 - the ECDSA signing service, attacker and relying party
# --------------------------------------------------------------------------- #
class EcdsaLab:
    def __init__(self):
        self.mode = None
        self.d = self.Q = self._k = None
        self.channel = []          # public channel: what the attacker can see
        self.d_rec = None

    def start(self, req):
        mode = req.get("mode", "vulnerable")
        if mode not in ("vulnerable", "patched"):
            raise ValueError("unknown mode")
        self.mode = mode
        self.d, self.Q = E.generate_keypair()
        self._k = secrets.randbelow(E.N - 1) + 1 if mode == "vulnerable" else None
        self.channel, self.d_rec = [], None
        return {"mode": mode, "qx": hx(self.Q[0]), "qy": hx(self.Q[1]), "d": hx(self.d)}

    def _require(self):
        if self.mode is None:
            raise ValueError("Start the signing service first.")

    def sign(self, req):
        self._require()
        msg = req["message"].encode()
        if self.mode == "vulnerable":
            k = self._k                                   # BUG: same k every call
        else:
            k = E.rfc6979_nonce(self.d, msg)              # FIX: RFC 6979
        r, s = E.ecdsa_sign(msg, self.d, k)
        valid = lib_verify(E.to_crypto_public_key(self.Q), msg, (r, s))
        self.channel.append((msg, (r, s)))
        return {"message": msg.decode(), "r": hx(r), "s": hx(s), "valid": valid,
                "index": len(self.channel)}

    def attack(self, _):
        self._require()
        if len(self.channel) < 2:
            raise ValueError("The attacker needs at least two signatures on the public channel.")
        t = time.perf_counter()
        pair = find_reused_nonce(self.channel)
        out = {"scanned": len(self.channel), "reused": pair is not None}
        if pair:
            (m1, s1), (m2, s2) = pair
            h1, h2 = E.hash_to_int(m1), E.hash_to_int(m2)
            k = recover_nonce(m1, s1, m2, s2)
            d = recover_private_key(m1, s1, k)
            out.update({"m1": m1.decode(), "m2": m2.decode(), "r": hx(s1[0]),
                        "s1": hx(s1[1]), "s2": hx(s2[1]), "h1": hx(h1), "h2": hx(h2),
                        "k": hx(k), "d": hx(d)})
        else:
            (m1, s1), (m2, s2) = self.channel[0], self.channel[1]
            try:
                recover_nonce(m1, s1, m2, s2)
            except ValueError as exc:
                out["refused"] = str(exc)
            # Force the formulas anyway, pretending r1 == r2
            k = recover_nonce(m1, s1, m2, (s1[0], s2[1]))
            d = recover_private_key(m1, s1, k)
            out.update({"m1": m1.decode(), "m2": m2.decode(),
                        "r1": hx(s1[0]), "r2": hx(s2[0]), "k": hx(k), "d": hx(d)})
        matches = E.scalar_mult(d) == self.Q
        self.d_rec = d
        out.update({"matches": matches, "real_d": hx(self.d),
                    "ms": round((time.perf_counter() - t) * 1000)})
        return out

    def forge(self, req):
        self._require()
        if self.d_rec is None:
            raise ValueError("Run the attack first to obtain a key.")
        msg = req["message"].encode()
        stolen = E.to_crypto_private_key(self.d_rec)           # import into a normal library
        r, s = E.der_to_sig(stolen.sign(msg, ec.ECDSA(hashes.SHA256())))
        accepted = lib_verify(E.to_crypto_public_key(self.Q), msg, (r, s))
        return {"message": msg.decode(), "r": hx(r), "s": hx(s), "accepted": accepted}

    def crosscheck(self, req):
        self._require()
        msg = req["message"].encode()
        ours = E.ecdsa_sign_rfc6979(msg, self.d)
        try:
            lib = E.der_to_sig(E.to_crypto_private_key(self.d).sign(
                msg, ec.ECDSA(hashes.SHA256(), deterministic_signing=True)))
        except TypeError:
            return {"supported": False}
        return {"supported": True, "ours_r": hx(ours[0]), "ours_s": hx(ours[1]),
                "lib_r": hx(lib[0]), "lib_s": hx(lib[1]), "identical": ours == lib}


# --------------------------------------------------------------------------- #
# Demo 4 - textbook RSA vs RSA-PSS
# --------------------------------------------------------------------------- #
class RsaLab:
    def __init__(self):
        self.key = None

    def run(self, req):
        m1, m2 = int(req["m1"]), int(req["m2"])
        if not (1 < m1 < 10**12 and 1 < m2 < 10**12):
            raise ValueError("Use integers between 2 and 10^12.")
        if self.key is None:
            self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv = self.key.private_numbers()
        n, e, d = priv.public_numbers.n, priv.public_numbers.e, priv.d
        s1, s2 = pow(m1, d, n), pow(m2, d, n)
        fm, fs = m1 * m2, s1 * s2 % n
        textbook_ok = pow(fs, e, n) == fm % n
        b1, b2, bf = str(m1).encode(), str(m2).encode(), str(fm).encode()
        p1 = int.from_bytes(self.key.sign(b1, PSS, hashes.SHA256()), "big")
        p2 = int.from_bytes(self.key.sign(b2, PSS, hashes.SHA256()), "big")
        pf = (p1 * p2 % n).to_bytes(256, "big")
        try:
            self.key.public_key().verify(pf, bf, PSS, hashes.SHA256())
            pss_ok = True
        except InvalidSignature:
            pss_ok = False
        return {"m1": m1, "m2": m2, "forged_m": fm,
                "s1": f"{s1:x}", "s2": f"{s2:x}", "forged_s": f"{fs:x}",
                "textbook_ok": textbook_ok, "pss_ok": pss_ok,
                "p1": f"{p1:x}", "p2": f"{p2:x}", "pss_forged": pf.hex()}


def run_tests(_):
    buf = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"))
    t = time.perf_counter()
    result = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    return {"output": buf.getvalue(), "run": result.testsRun,
            "failures": len(result.failures) + len(result.errors),
            "ok": result.wasSuccessful(), "ms": round((time.perf_counter() - t) * 1000)}


CORRECT, LAB, RSALAB = CorrectUse(), EcdsaLab(), RsaLab()
ROUTES = {
    "/api/demo1/keygen": CORRECT.keygen,
    "/api/demo1/sign": CORRECT.sign,
    "/api/demo1/verify": CORRECT.verify,
    "/api/demo1/eve_sign": CORRECT.eve_sign,
    "/api/ecdsa/start": LAB.start,
    "/api/ecdsa/sign": LAB.sign,
    "/api/ecdsa/attack": LAB.attack,
    "/api/ecdsa/forge": LAB.forge,
    "/api/ecdsa/crosscheck": LAB.crosscheck,
    "/api/rsa/run": RSALAB.run,
    "/api/tests": run_tests,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        page = PAGES.get(self.path.split("?")[0])
        if page:
            self._send(200, (WEB / page).read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        fn = ROUTES.get(self.path)
        if fn is None:
            return self._send(404, b'{"error":"not found"}', "application/json")
        try:
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length) or b"{}")
            with LOCK:
                data = fn(req)
            self._send(200, json.dumps(data).encode(), "application/json")
        except Exception as exc:  # report errors to the GUI instead of crashing
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")

    def log_message(self, fmt, *args):
        sys.stderr.write("  [web] " + fmt % args + "\n")


def main():
    port = 8000
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Digital signature demo GUI running at {url}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
