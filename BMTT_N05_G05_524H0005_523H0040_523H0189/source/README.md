# Digital Signatures in Practice: Final Demonstration

**Course:** Introduction to Information Security, Ton Duc Thang University
**Instructor:** Ph.D. Huynh Ngoc Tu
**Group:** N05_G05: Trieu Ngoc Van Anh (524H0005), Duong Tran Quoc Khanh (523H0040), Nguyen Vo Thanh Tu (523H0189)

This project puts the midterm theory report into practice. It contains:

| # | Script | What it shows |
|---|--------|---------------|
| 1 | `demo1_correct_use.py` | RSA-2048 (PSS) and ECDSA P-256 sign and verify correctly. A tampered message and an impostor's key are both rejected. |
| 2 | `demo2_nonce_reuse_attack.py` | **Attack:** a buggy signer reuses the ECDSA nonce `k`. The private key is recovered from two public signatures, and a forged invoice is accepted by the `cryptography` library. |
| 3 | `demo3_defense_rfc6979.py` | **Patch:** RFC 6979 deterministic nonces. The same attack fails, and the result is cross-checked byte-for-byte against `cryptography` (`deterministic_signing=True`). |
| 4 | `demo4_rsa_textbook_vs_pss.py` | Bonus: textbook RSA multiplicative forgery, which RSA-PSS blocks. |
| – | `openssl_demo.sh` | The same sign/verify/tamper flow using only the OpenSSL CLI. |
| – | `tests/` | Unit tests, including the official RFC 6979 A.2.5 test vector. |

## Requirements
* Python 3.10+ (tested on Python 3.11.9, Windows 10 and macOS). On macOS/Linux use `python3` instead of `python`
* `cryptography >= 44` (tested with 50.0.1)
* Optional: OpenSSL 3.x for `openssl_demo.sh` (it ships with Git for Windows)

No network access, VM or server is needed. Everything runs locally and offline.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

## Run

### Web GUI (recommended for the live demo)
```bash
python web_demo.py               # macOS/Linux: python3 web_demo.py
```
This opens `http://127.0.0.1:8000` in the browser (options: `--port 8080`, `--no-browser`).

The page tells the demo as a story with four actors: the signer (Alice / SecureSign), the Internet, the attacker Eve,
and the verifier (Bob / the bank). Each click runs one real step and explains the result in plain language.

| Scene | Steps |
|-------|-------|
| 1 · How it works | Alice creates keys → signs a contract → Bob verifies (valid) → Eve changes 1,000 to 9,000 USD (rejected) → Eve signs with her own key (rejected) |
| 2 · The attack | SecureSign (reuses k) starts → signs invoice #1001 → signs invoice #1002 (same r) → Eve recovers the private key → forged 1,000,000 USD invoice is accepted |
| 3 · The fix | Same steps with RFC 6979: r differs → wrong key → forgery rejected → byte-identical to the `cryptography` library |
| 4 · Bonus: RSA | sign(100) × sign(50) = valid signature on 5,000 with textbook RSA; RSA-PSS rejects it |

Controls: **→ / Space / Enter** next step, **R** restart the scene, **M** show or hide the math (equations and full
values), **EN / VI** switches the language. Values are shown as coloured fingerprints, so equal values have equal
colours. Deep links: `#correct`, `#attack`, `#defense`, `#rsa`; `#attack/5` opens a scene and runs its first 5 steps.

The **Technical view** (link in the footer, or `http://127.0.0.1:8000/advanced`) shows full hex values, editable
messages and a button that runs the unit tests.

Every button calls the real project code (`ecc_core.py`, `attack.py`) and the `cryptography` library; nothing is
pre-recorded. The verifier always uses the `cryptography` library, never our own code.

### Console
```bash
python run_all.py --pause        # full live demo, pauses after each step
python demo2_nonce_reuse_attack.py
python -m unittest discover -s tests -v
bash openssl_demo.sh
```
Generated keys, signatures and intercepted/forged data are written to `output/`.

## File layout
```
ecc_core.py      P-256 arithmetic, ECDSA with explicit nonce, RFC 6979 (educational)
attack.py        nonce-reuse detection and private-key recovery
ui.py            console formatting helpers
web_demo.py      local web GUI server (standard library only)
web/index.html   story-mode demo page (EN/VI)
web/advanced.html technical view (full values, unit tests)
demo1..demo4     demonstration scripts
run_all.py       runs all demos in order
tests/           unittest suite
```

> `ecc_core.py` is intentionally minimal and **not constant-time**. It exists only because audited
> libraries do not let the caller choose `k`, which we need in order to reproduce the bug. Do not use it in production.
