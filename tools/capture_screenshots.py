"""Capture every figure used in the final report, from the real running system.

Usage (from final-BMTT/tools):
    .venv/bin/python capture_screenshots.py

What it does
  1. Starts SecureSign on a free local port with a throw-away database and storage folder.
  2. Drives the real web app with Playwright (installed Google Chrome, headless):
     Alice and Bob register, Alice creates an RSA key in the browser, proves possession,
     signs a PDF, sends it to Bob; Bob trusts Alice's key, verifies the document and a
     tampered copy; the admin opens the user list; then the Security Lab scenes run.
  3. Runs the console demos, the test suite and an OpenSSL check of the forged PDF and
     renders their coloured output as terminal screenshots.
All accounts and passwords are random test values that exist only for this run.
"""
import html
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "BMTT_N05_G05_524H0005_523H0040_523H0189"
SRC = SUB / "source"
SHOTS = SUB / "screenshots"
PY = SRC / ".venv" / "bin" / "python"
sys.path.insert(0, str(SRC))
from backend.lab.pdf_tools import make_pdf  # noqa: E402

CONTRACT = ("CONTRACT #2026-11\n"
            "Alice Nguyen agrees to pay Bob Tran 1,000 USD on 30/11/2026\n"
            "for the delivery of 20 laptops (order SO-7781).")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------- terminal rendering
ANSI = re.compile(r"\x1b\[([0-9;]*)m")
COLORS = {"31": "#ff6b6b", "32": "#5af78e", "33": "#f3c969", "35": "#ff79c6", "36": "#57c7ff", "34": "#79a6ff"}


def ansi_to_html(text: str) -> str:
    out, pos, open_span = [], 0, False
    for m in ANSI.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        pos = m.end()
        if open_span:
            out.append("</span>"); open_span = False
        codes = [c for c in m.group(1).split(";") if c]
        if codes and codes != ["0"]:
            color = next((COLORS[c] for c in codes if c in COLORS), "#e6e6e6")
            weight = "700" if "1" in codes else "400"
            out.append(f'<span style="color:{color};font-weight:{weight}">'); open_span = True
    out.append(html.escape(text[pos:]))
    if open_span:
        out.append("</span>")
    return "".join(out)


TERM = """<html><head><style>
body{margin:0;background:#fff}
.w{width:%(width)dpx;background:#0c0c0c;border-radius:10px;overflow:hidden;font:14px/1.55 Menlo,Consolas,monospace;color:#e6e6e6}
.bar{background:#2b2b2b;padding:9px 14px;color:#cfcfcf;font:13px -apple-system,Segoe UI,sans-serif;display:flex;gap:8px;align-items:center}
.bar i{width:12px;height:12px;border-radius:50%%;display:inline-block}
pre{margin:0;padding:14px 18px 18px;white-space:pre-wrap;word-break:break-all}
.p{color:#79a6ff;font-weight:700}
</style></head><body><div class="w" id="t"><div class="bar"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>&nbsp; %(title)s</div><pre>%(body)s</pre></div></body></html>"""


def run_console(cmds, cwd=SRC, env_extra=None):
    """Run shell commands and return a transcript with prompts, like a real terminal session."""
    env = dict(os.environ, FORCE_COLOR="1", PYTHONUNBUFFERED="1", PY_COLORS="1", **(env_extra or {}))
    env["PATH"] = f"{SRC / '.venv' / 'bin'}:{env['PATH']}"
    parts = []
    for shown, real in cmds:
        res = subprocess.run(real, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
        parts.append(f"\x1b[1;34m$ {shown}\x1b[0m\n" + (res.stdout + res.stderr).rstrip("\n"))
    return "\n".join(parts)


def term_shot(page, transcript, out, title="Terminal — zsh — Python 3.11.9 (macOS)", width=940, keep=None):
    lines = transcript.split("\n")
    if keep:
        lines = keep(lines)
    body = ansi_to_html("\n".join(lines))
    page.set_content(TERM % {"width": width, "title": html.escape(title), "body": body})
    page.locator("#t").screenshot(path=str(SHOTS / out))
    print("  saved", out)


def between(start, end=None, head=None):
    """Keep the prompt/banner (`head` lines) plus the lines from `start` up to (not incl.) `end`."""
    def cut(lines):
        i = next(k for k, l in enumerate(lines) if start in l)
        j = next((k for k, l in enumerate(lines) if end and end in l and k > i), len(lines))
        return (lines[:head] + ["   ..."] if head else []) + lines[i:j]
    return cut


# --------------------------------------------------------------------------- app helpers
def register(page, base, name, email, password):
    page.goto(base)
    page.click("#auth-switch-button")
    page.fill("#register-name", name)
    page.fill("#register-email", email)
    page.fill("#register-password", password)
    page.fill("#register-confirm", password)
    page.click("#register-button")
    page.wait_for_selector("#app-shell:not(.hidden)")
    page.wait_for_timeout(600)


def go(page, name):
    page.click(f'[data-page="{name}"]')
    page.wait_for_timeout(700)


def shot_main(page, out, full=False):
    page.wait_for_timeout(400)
    if full:
        page.screenshot(path=str(SHOTS / out), full_page=True)
    else:
        page.screenshot(path=str(SHOTS / out))
    print("  saved", out)


def lab(page, base, deep, out):
    page.goto(f"{base}/lab?{secrets.token_hex(3)}#{deep}")
    page.wait_for_function("document.title.includes('[ready]')", timeout=60000)
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / out), full_page=True)
    print("  saved", out)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="securesign-shots-"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    admin_pw, alice_pw, bob_pw, key_pw = (secrets.token_urlsafe(18) for _ in range(4))
    env = dict(os.environ, SECURESIGN_STORAGE_DIR=str(tmp / "storage"),
               DATABASE_URL=f"sqlite:///{tmp / 'shots.db'}", APP_ENV="development",
               ADMIN_EMAIL="admin@securesign-demo.com", ADMIN_PASSWORD=admin_pw, ADMIN_NAME="SecureSign Admin",
               SECURESIGN_DEMO_ACCOUNTS="false")
    server = subprocess.Popen([str(PY), "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                              cwd=SRC, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1); break
            except Exception:
                time.sleep(0.3)
        files = tmp / "files"; files.mkdir()
        (files / "contract-SO-7781.pdf").write_bytes(make_pdf(CONTRACT, title="SecureSign Contract"))
        (files / "contract-SO-7781-tampered.pdf").write_bytes(
            make_pdf(CONTRACT.replace("1,000 USD", "9,000 USD"), title="SecureSign Contract"))
        SHOTS.mkdir(exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            opts = dict(viewport={"width": 1280, "height": 760}, device_scale_factor=2, accept_downloads=True, locale="vi-VN", bypass_csp=True)
            alice_ctx, bob_ctx, admin_ctx = (browser.new_context(**opts) for _ in range(3))
            alice, bob, admin = alice_ctx.new_page(), bob_ctx.new_page(), admin_ctx.new_page()

            print("SecureSign web app")
            register(alice, base, "Alice Nguyen", "alice@securesign-demo.com", alice_pw)
            register(bob, base, "Bob Tran", "bob@securesign-demo.com", bob_pw)
            shot_main(alice, "fig02_dashboard.png")

            # Alice: key pair generated and encrypted in the browser, then proof-of-possession registration
            go(alice, "keys")
            alice.fill("#key-owner", "Alice - contract signing key")
            alice.fill("#new-key-password", key_pw)
            alice.fill("#confirm-key-password", key_pw)
            alice.click("#generate-keys")
            alice.wait_for_selector("#generated-key-result:not(.hidden)", timeout=60000)
            with alice.expect_download() as d:
                alice.click("#download-private")
            d.value.save_as(files / "alice.key.json")
            alice.click("#register-generated")
            alice.wait_for_function("document.querySelector('#my-keys-list').innerText.includes('Alice - contract')", timeout=30000)
            shot_main(alice, "fig03_keys.png")

            # Alice signs the PDF (RSA-PSS in the browser, server re-verifies)
            go(alice, "sign")
            alice.set_input_files("#sign-pdf", str(files / "contract-SO-7781.pdf"))
            alice.set_input_files("#sign-private-key", str(files / "alice.key.json"))
            alice.fill("#sign-password", key_pw)
            alice.click("#sign-button")
            alice.wait_for_selector("#sign-result:not(.hidden)", timeout=60000)
            with alice.expect_download() as d:
                alice.click("#download-signature")
            d.value.save_as(files / "contract-SO-7781.sig")
            shot_main(alice, "fig04_sign.png")

            # Alice sends the signed PDF to Bob
            go(alice, "send")
            alice.fill("#send-recipient", "bob@securesign-demo.com")
            alice.select_option("#send-key-select", index=1)
            alice.set_input_files("#send-pdf", str(files / "contract-SO-7781.pdf"))
            alice.set_input_files("#send-signature", str(files / "contract-SO-7781.sig"))
            alice.fill("#send-message", "Hợp đồng SO-7781 đã ký, nhờ anh kiểm tra.")
            alice.click("#send-button")
            alice.wait_for_selector("#notice.success", timeout=30000)
            shot_main(alice, "fig05_send.png")

            # Bob trusts Alice's key (after comparing the fingerprint), then verifies the received PDF
            go(bob, "keys")
            bob.locator("#directory-body button", has_text="Đánh dấu tin cậy").first.click()
            bob.wait_for_selector("#notice.success")
            go(bob, "inbox")
            bob.locator("#documents-body button", has_text="Kiểm tra").first.click()
            bob.wait_for_selector("#notice.success", timeout=30000)
            bob.wait_for_timeout(600)
            shot_main(bob, "fig06_inbox_verified.png")

            # Bob checks a tampered copy (1,000 -> 9,000 USD) with the same signature
            go(bob, "verify")
            bob.set_input_files("#verify-pdf", str(files / "contract-SO-7781-tampered.pdf"))
            bob.set_input_files("#verify-signature", str(files / "contract-SO-7781.sig"))
            bob.select_option("#verify-key-select", index=1)
            bob.click("#verify-button")
            bob.wait_for_selector("#verify-result:not(.hidden)", timeout=30000)
            shot_main(bob, "fig07_verify_tampered.png")

            # Bob downloads the server-signed receipt of the delivery and checks it (non-repudiation)
            go(bob, "inbox")
            with bob.expect_download() as d:
                bob.locator("#documents-body button", has_text="Biên nhận").first.click()
            d.value.save_as(files / "receipt-sent.json")
            go(bob, "verify")
            bob.set_input_files("#receipt-file", str(files / "receipt-sent.json"))
            bob.click("#verify-receipt-button")
            bob.wait_for_selector("#receipt-result:not(.hidden)", timeout=30000)
            bob.locator(".receipt-section").scroll_into_view_if_needed()
            bob.locator(".receipt-section").screenshot(path=str(SHOTS / "fig19_receipt_verify.png"))
            print("  saved fig19_receipt_verify.png")

            # Administrator view (roles, suspension) and Alice's audit trail
            admin.goto(base)
            admin.fill("#login-email", "admin@securesign-demo.com")
            admin.fill("#login-password", admin_pw)
            admin.click("#login-button")
            admin.wait_for_selector("#app-shell:not(.hidden)")
            go(admin, "admin")
            shot_main(admin, "fig08_admin.png")
            admin.click("#check-evidence")
            admin.wait_for_selector("#evidence-check.ok, #evidence-check.broken", timeout=30000)
            admin.locator(".evidence-panel").scroll_into_view_if_needed()
            admin.locator(".evidence-panel").screenshot(path=str(SHOTS / "fig21_admin_evidence.png"))
            print("  saved fig21_admin_evidence.png")
            go(alice, "history")
            shot_main(alice, "fig09_history.png")

            print("Security Lab")
            lab_opts = dict(viewport={"width": 1100, "height": 900}, device_scale_factor=2, accept_downloads=True, bypass_csp=True)
            lab_ctx = browser.new_context(**lab_opts)
            lab_ctx.add_cookies(alice_ctx.cookies())
            lp = lab_ctx.new_page()
            lab(lp, base, "correct/5", "fig10_lab_correct.png")
            lab(lp, base, "attack/5", "fig12_lab_attack.png")
            for name in ("forged.pdf", "forged.sig", "public.pem"):
                (files / f"lab-{name}").write_bytes(lab_ctx.request.get(f"{base}/api/lab/ecdsa/files/{name}").body())
            lab(lp, base, "defense/6", "fig15_lab_defense.png")
            lab(lp, base, "rsa/3", "fig16_lab_rsa.png")
            lab(lp, base, "keysub/3", "fig17_lab_keysub.png")
            lab(lp, base, "evidence/4", "fig18_lab_evidence.png")

            print("Terminal")
            tp = browser.new_page(device_scale_factor=2)
            tp.goto((Path(__file__).parent / "architecture.html").as_uri())
            tp.locator("#d").screenshot(path=str(SHOTS / "fig00_architecture.png"))
            print("  saved fig00_architecture.png")
            t = run_console([("python -m pytest -v", "python -m pytest -v -p no:cacheprovider")])
            t = re.sub(r"^platform .*\n|^cachedir: .*\n|^rootdir: .*\n|^plugins: .*\n", "", t, flags=re.M)
            term_shot(tp, t, "fig01_tests.png", width=1000)
            d2 = run_console([("python demos/demo2_nonce_reuse_attack.py", "python demos/demo2_nonce_reuse_attack.py")])
            term_shot(tp, d2, "fig11_demo2_attack.png", keep=between("Step 3", None, head=4))
            off = files
            t = run_console([
                ("ls lab-*", "ls lab-*"),
                ("openssl dgst -sha256 -verify lab-public.pem -signature lab-forged.sig lab-forged.pdf",
                 "openssl dgst -sha256 -verify lab-public.pem -signature lab-forged.sig lab-forged.pdf"),
                ("LC_ALL=C sed 's/1,000,000/9,000,000/' lab-forged.pdf > edited.pdf && openssl dgst -sha256 -verify lab-public.pem -signature lab-forged.sig edited.pdf",
                 "LC_ALL=C sed 's/1,000,000/9,000,000/' lab-forged.pdf > edited.pdf && openssl dgst -sha256 -verify lab-public.pem -signature lab-forged.sig edited.pdf"),
            ], cwd=off)
            term_shot(tp, t, "fig13_openssl_forgery.png", title="Terminal — zsh — LibreSSL 3.3.6 (independent verifier)")
            d3 = run_console([("python demos/demo3_defense_rfc6979.py", "python demos/demo3_defense_rfc6979.py")])
            term_shot(tp, d3, "fig14_demo3_defense.png")
            # Offline verification of Alice's signing receipt, with the server key fetched once
            hist = alice_ctx.request.get(f"{base}/api/history").json()["items"]
            seq = next(h["receipt_seq"] for h in hist if h["event_type"] == "SIGN" and h["receipt_seq"])
            (files / f"securesign-receipt-{seq}.json").write_bytes(alice_ctx.request.get(f"{base}/api/receipts/{seq}").body())
            (files / "server-receipt-key.pem").write_text(alice_ctx.request.get(f"{base}/api/receipts/server-key").json()["public_key_pem"])
            t = run_console([
                (f"python demos/verify_receipt.py securesign-receipt-{seq}.json --server-key server-receipt-key.pem --pdf contract-SO-7781.pdf",
                 f"python {SRC / 'demos' / 'verify_receipt.py'} securesign-receipt-{seq}.json --server-key server-receipt-key.pem --pdf contract-SO-7781.pdf"),
            ], cwd=files)
            term_shot(tp, t, "fig20_verify_receipt_cli.png")
            browser.close()
    finally:
        server.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
