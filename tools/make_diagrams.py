"""Draw the flow diagrams used in the report (sequence diagrams, rendered to PNG).

Usage (from final-BMTT/tools):  .venv/bin/python make_diagrams.py
Output: ../BMTT_N05_G05_524H0005_523H0040_523H0189/screenshots/flow_*.png and fig00_architecture.png
"""
import html
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SHOTS = HERE.parent / "BMTT_N05_G05_524H0005_523H0040_523H0189" / "screenshots"

COL = {"blue": ("#eef5ff", "#7fa9e6"), "grey": ("#f4f5f7", "#b8bec8"), "red": ("#fff0f1", "#e48d95"),
       "green": ("#edf9f2", "#86cba3"), "amber": ("#fff7e6", "#e3b55c"), "violet": ("#f3f0ff", "#a99be8")}
INK = {"bad": "#c53b45", "good": "#168653", "normal": "#2b3d55", "note": "#6b7a8f"}
W, LEFT, TOP, ROW = 1180, 40, 150, 46
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def esc(t):
    return html.escape(t)


def sequence(title, actors, steps, verdicts=(), height_extra=0):
    """actors: [(name, subtitle, colour)]; steps: tuples
         ("msg", from, to, label, tone)        arrow between lifelines
         ("self", actor, label, tone)          action box on one lifeline
         ("sep", label)                        section divider
    verdicts: [(tone, text)] boxes under the diagram."""
    n = len(actors)
    span = (W - 2 * LEFT) / n
    xs = [LEFT + span * (i + 0.5) for i in range(n)]
    rows = len(steps)
    h = TOP + rows * ROW + 30 + len(verdicts) * 52 + height_extra
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" font-family="{FONT}">',
           '<defs>' + "".join(
               f'<marker id="a{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for k, c in INK.items()) + '</defs>',
           f'<rect width="{W}" height="{h}" fill="#ffffff"/>',
           f'<text x="{LEFT}" y="34" font-size="20" font-weight="700" fill="#142b4a">{esc(title)}</text>']
    life_end = TOP + rows * ROW + 10
    for x, (name, sub, colour) in zip(xs, actors):
        bg, bd = COL[colour]
        out.append(f'<line x1="{x}" y1="{108}" x2="{x}" y2="{life_end}" stroke="#c9d3e1" stroke-width="2" stroke-dasharray="6 6"/>')
        out.append(f'<rect x="{x - span / 2 + 10}" y="56" width="{span - 20}" height="52" rx="10" fill="{bg}" stroke="{bd}" stroke-width="2"/>')
        out.append(f'<text x="{x}" y="78" text-anchor="middle" font-size="15" font-weight="700" fill="#142b4a">{esc(name)}</text>')
        out.append(f'<text x="{x}" y="97" text-anchor="middle" font-size="11.5" fill="#5d6d83">{esc(sub)}</text>')
    y = TOP
    for st in steps:
        kind = st[0]
        if kind == "msg":
            _, a, b, label, tone = st
            x1, x2 = xs[a], xs[b]
            pad = 8 if x2 > x1 else -8
            colour = INK[tone]
            out.append(f'<line x1="{x1 + pad}" y1="{y + 14}" x2="{x2 - pad}" y2="{y + 14}" stroke="{colour}" stroke-width="2.2" marker-end="url(#a{tone})"/>')
            out.append(f'<text x="{(x1 + x2) / 2}" y="{y + 6}" text-anchor="middle" font-size="12.5" fill="{colour}" font-weight="600">{esc(label)}</text>')
        elif kind == "self":
            _, a, label, tone = st
            colour = INK[tone]
            bw = min(span * 1.55, 9 * len(label) + 30)
            fill = {"bad": "#fff0f1", "good": "#edf9f2"}.get(tone, "#f6f8fb")
            bx = min(max(xs[a] - bw / 2, LEFT), W - LEFT - bw)     # keep the box inside the frame
            out.append(f'<rect x="{bx}" y="{y - 4}" width="{bw}" height="30" rx="7" fill="{fill}" stroke="{colour}" stroke-width="1.4"/>')
            out.append(f'<text x="{bx + bw / 2}" y="{y + 15}" text-anchor="middle" font-size="12.5" fill="{colour}">{esc(label)}</text>')
        elif kind == "sep":
            out.append(f'<line x1="{LEFT}" y1="{y + 12}" x2="{W - LEFT}" y2="{y + 12}" stroke="#e3e8ef" stroke-width="1.5"/>')
            out.append(f'<rect x="{LEFT}" y="{y}" width="{9 * len(st[1]) + 24}" height="24" rx="12" fill="#142b4a"/>')
            out.append(f'<text x="{LEFT + 12}" y="{y + 16}" font-size="12" font-weight="700" fill="#ffffff">{esc(st[1])}</text>')
        y += ROW
    y = life_end + 18
    for tone, text in verdicts:
        colour = INK[tone]
        fill = {"bad": "#fff0f1", "good": "#edf9f2"}.get(tone, "#f6f8fb")
        out.append(f'<rect x="{LEFT}" y="{y}" width="{W - 2 * LEFT}" height="40" rx="9" fill="{fill}" stroke="{colour}" stroke-width="1.5"/>')
        out.append(f'<text x="{LEFT + 16}" y="{y + 25}" font-size="13.5" font-weight="600" fill="{colour}">{esc(text)}</text>')
        y += 52
    out.append("</svg>")
    return "\n".join(out)


A, S, L, E, B = 0, 1, 2, 3, 4

DIAGRAMS = {
    "flow_signing": sequence(
        "Signing workflow: key registration, signing, delivery and receipts",
        [("Alice (browser)", "Web Crypto, private key stays here", "blue"), ("SecureSign server", "FastAPI + cryptography", "violet"),
         ("Evidence log", "hash chain, server-signed", "amber"), ("Bob (browser)", "recipient / verifier", "green")],
        [("sep", "1 · Key registration with proof-of-possession"),
         ("self", 0, "generate RSA-PSS 2048 or ECDSA P-256 key pair", "normal"),
         ("self", 0, "encrypt private key: PBKDF2 (310,000) → AES-256-GCM → .key.json", "normal"),
         ("msg", 0, 1, "POST /api/keys/challenge", "normal"),
         ("msg", 1, 0, "one-time random challenge (5 min, single use)", "normal"),
         ("msg", 0, 1, "public key + signature on the challenge", "normal"),
         ("self", 1, "verify_proof_of_possession() ✓  key bound to Alice", "good"),
         ("msg", 1, 2, "receipt #1 KEY_REGISTERED", "normal"),
         ("sep", "2 · Signing and delivery"),
         ("self", 0, "decrypt key locally, sign SHA-256(PDF) → .sig", "normal"),
         ("msg", 0, 1, "PDF + .sig (+ recipient bob@…)", "normal"),
         ("self", 1, "verify_signature() with Alice's registered key ✓", "good"),
         ("msg", 1, 2, "receipt #2 PDF_SIGNED, #3 DOCUMENT_SENT", "normal"),
         ("msg", 1, 0, "receipt (server time, PDF SHA-256, key fingerprint)", "normal"),
         ("msg", 1, 3, "document in Bob's inbox (only Alice and Bob can read it)", "normal"),
         ("sep", "3 · Verification"),
         ("msg", 3, 1, "verify document", "normal"),
         ("self", 1, "signature valid ✓, key trusted by Bob?", "good"),
         ("msg", 1, 2, "receipt #4 DOCUMENT_VERIFIED", "normal")],
    ),
    "flow_tamper": sequence(
        "Attack 1 · Tampering with a signed PDF (integrity)",
        [("Alice", "signer", "blue"), ("Network / storage", "PDF + .sig in transit", "grey"),
         ("Eve", "attacker without Alice's key", "red"), ("Bob + SecureSign", "verifier", "green")],
        [("msg", 0, 1, "contract.pdf (1,000 USD) + contract.sig", "normal"),
         ("msg", 1, 2, "intercepts the PDF", "bad"),
         ("self", 2, "edits one character: 1,000 → 9,000 USD", "bad"),
         ("msg", 2, 3, "tampered PDF + Alice's original .sig", "bad"),
         ("self", 3, "SHA-256(tampered PDF) ≠ hash signed by Alice", "good"),
         ("self", 3, "verify_signature() → INVALID", "good")],
        [("good", "Result: rejected. One changed character flips about half of the 256 hash bits, so the old signature never matches."),
         ("normal", "Eve cannot re-sign: a new valid signature needs Alice's private key, which never leaves Alice's browser.")],
    ),
    "flow_keysub": sequence(
        "Attack 2 · Key substitution: claiming someone else's public key (authentication)",
        [("Alice", "real key owner", "blue"), ("Key directory", "public keys are public", "grey"),
         ("Eve", "has only Alice's PUBLIC key", "red"), ("SecureSign server", "POST /api/keys", "violet")],
        [("msg", 0, 1, "Alice's public key (registered with proof)", "normal"),
         ("msg", 1, 2, "Eve downloads Alice's public key (PEM)", "bad"),
         ("msg", 2, 3, "register Alice's key under Eve's account", "bad"),
         ("msg", 3, 2, "one-time challenge", "normal"),
         ("self", 2, "can only sign it with EVE's private key", "bad"),
         ("msg", 2, 3, "Alice's public key + proof signed by Eve", "bad"),
         ("self", 3, "verify_proof_of_possession() fails → 400", "good"),
         ("self", 3, "fingerprint already owned by Alice → 409", "good")],
        [("bad", "Without the check: Alice's PDFs would verify as \"signed by Eve\"; Eve could claim them and Alice could deny them."),
         ("good", "Result: rejected. Only the holder of the private key can answer a fresh challenge; an old proof cannot be replayed.")],
    ),
    "flow_repudiation": sequence(
        "Attack 3 · Repudiation and log tampering (non-repudiation)",
        [("Alice", "signer who wants to deny", "blue"), ("SecureSign + evidence log", "entries #1…#n, signed + chained", "amber"),
         ("Mallory", "insider with database access", "red"), ("Judge / auditor", "has Bob's receipt + server key", "green")],
        [("msg", 0, 1, "signs contract.pdf → receipt #2 (time T, SHA-256, key)", "normal"),
         ("sep", "a · \"I never signed it\" / \"I signed it later\""),
         ("msg", 0, 3, "presents a receipt dated T + 7 days, signed with her own key", "bad"),
         ("self", 3, "receipt not signed by the SecureSign key → rejected", "good"),
         ("self", 3, "Bob's receipt #2: valid server signature, time T", "good"),
         ("sep", "b · Editing the log"),
         ("msg", 2, 1, "UPDATE entry #2: time → T + 7 days", "bad"),
         ("self", 1, "SHA-256(entry #2) ≠ entry_hash → broken at #2", "good"),
         ("msg", 2, 1, "also recompute hashes of #2, #3, …", "bad"),
         ("self", 1, "server signature on #2 invalid → still broken", "good"),
         ("msg", 3, 1, "compare Bob's receipt with entry #2", "normal"),
         ("self", 3, "entry_hash differs → tampering proven", "good")],
        [("good", "Result: the PDF signature proves WHO, the server receipt proves WHAT and WHEN, the hash chain proves the history was not rewritten."),
         ("normal", "Residual risk: whoever steals the server receipt key could rewrite everything → keep it in an HSM, anchor the chain head externally.")],
    ),
    "flow_nonce": sequence(
        "Attack 4 · ECDSA nonce reuse (why the ECDSA implementation matters)",
        [("Buggy ECDSA signer", "k chosen once, reused", "red"), ("Public", "signatures (r, s) are public", "grey"),
         ("Attacker", "public data only", "red"), ("SecureSign (Web Crypto)", "fresh random k per signature", "green")],
        [("msg", 0, 1, "sign(m1) = (r, s1),  sign(m2) = (r, s2)  → same r!", "bad"),
         ("msg", 1, 2, "two messages + two signatures", "bad"),
         ("self", 2, "k = (h1 − h2) / (s1 − s2) mod n", "bad"),
         ("self", 2, "d = (s1·k − h1) / r mod n  → private key", "bad"),
         ("self", 2, "forges a valid signature on any PDF", "bad"),
         ("sep", "SecureSign"),
         ("self", 3, "every ECDSA signature uses a new secret k", "good"),
         ("msg", 3, 1, "(r1, s1), (r2, s2) with r1 ≠ r2", "good"),
         ("self", 2, "2 equations, 3 unknowns → key cannot be solved", "good")],
        [("bad", "This is how Sony's PS3 signing key leaked in 2010: the mathematics of ECDSA was fine, the nonce was not."),
         ("good", "Defense: audited libraries only (Web Crypto, cryptography); RFC 6979 deterministic nonces where the library allows it.")],
    ),
    "flow_ratelimit": sequence(
        "Attack 5 · Password guessing behind a spoofed X-Forwarded-For (fixed bug)",
        [("Attacker", "script, one IP", "red"), ("SecureSign before the fix", "key = left-most XFF", "grey"),
         ("SecureSign after the fix", "key = TCP peer address", "green")],
        [("msg", 0, 1, "POST /login  X-Forwarded-For: 203.0.113.1", "bad"),
         ("msg", 0, 1, "POST /login  X-Forwarded-For: 203.0.113.2  (new value each time)", "bad"),
         ("self", 1, "new rate-limit bucket every request → never 429", "bad"),
         ("sep", "After the fix"),
         ("msg", 0, 2, "same 12 requests with spoofed XFF", "bad"),
         ("self", 2, "XFF ignored unless TRUST_PROXY_HEADERS (Caddy/Vercel)", "good"),
         ("self", 2, "requests 1–10 → 401, 11–12 → 429 Too Many Requests", "good")],
        [("good", "Result: unlimited online guessing is no longer possible; covered by tests/test_hardening.py.")],
    ),
}


def main():
    SHOTS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=2)
        for name, svg in DIAGRAMS.items():
            page.set_content(f'<html><body style="margin:0;background:#fff"><div id="d" style="display:inline-block">{svg}</div></body></html>')
            page.locator("#d").screenshot(path=str(SHOTS / f"{name}.png"))
            print("saved", name)
        page.goto((HERE / "architecture.html").as_uri())
        page.locator("#d").screenshot(path=str(SHOTS / "fig00_architecture.png"))
        print("saved fig00_architecture")
        browser.close()


if __name__ == "__main__":
    main()
