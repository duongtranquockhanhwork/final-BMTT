"""Build the final report in the midterm report's format (cover, front matter, chapters).
Usage: python build_report.py <midterm.docx> <screenshots dir> <out.docx> [pages.json]
pages.json (optional) maps heading/figure keys -> page labels for the TOC / list of figures."""
import copy, json, re, sys
import docx
from docx.shared import Inches
from docx.oxml.ns import qn
from lxml import etree

MID, SHOTS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PAGES = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}

d = docx.Document(MID)
body = d.element.body
els = list(body.iterchildren())
T_CODE = copy.deepcopy(els[102])
T_DATA = copy.deepcopy(els[135])
T_ABBR = copy.deepcopy(els[67])
TOC = els[63]

# ------------------------------------------------------------------ front matter text
def replace_in_par(p, old, new):
    """Replace text that may span runs: collapse runs' text into the first run."""
    runs = p.findall('.//' + qn('w:r'))
    full = ''.join(t.text or '' for r in runs for t in r.findall(qn('w:t')))
    if old not in full:
        return False
    first = True
    for r in runs:
        for t in r.findall(qn('w:t')):
            if first:
                t.text = full.replace(old, new); t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve'); first = False
            else:
                t.text = ''
    return True

REPL = [
    ("MIDTERM THEORY REPORT", "FINAL DEMONSTRATION AND TECHNICAL REPORT"),
    ("MIDTERM REPORT", "FINAL REPORT"),
    ("September 2026", "November 2026"),
    ("throughout the preparation of this midterm report on digital signatures",
     "throughout the midterm and final phases of our project on digital signatures"),
    ("His constructive feedback helped us look beyond the textbook definitions of RSA and ECC and understand why correct implementation, not just correct algorithm choice, is what ultimately keeps a signature scheme secure.",
     "His constructive feedback on our midterm theory report helped us turn the analysis of RSA and ECC into a working demonstration, and showed us why correct implementation, not just correct algorithm choice, is what ultimately keeps a signature scheme secure."),
    ("We hereby declare that this report is our own work",
     "We hereby declare that this report and the accompanying source code are our own work"),
]
for el in els[:63]:
    for p in [el] if el.tag == qn('w:p') else el.iter(qn('w:p')):
        for o, n in REPL:
            replace_in_par(p, o, n)

# each cover overflows by ~1 line in some renderers -> drop one empty spacer line per cover
for i in (19, 40):
    if not ''.join(els[i].itertext()).strip():
        body.remove(els[i])

# remove old body after TOC (keep the section-break paragraph #71 and final sectPr)
SECT_BREAK = els[71]
for el in els[64:]:
    if el is SECT_BREAK or el.tag == qn('w:sectPr'):
        continue
    body.remove(el)
final_sectpr = body.find(qn('w:sectPr'))

# ------------------------------------------------------------------ builders
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def E(tag, **attrs):
    el = etree.SubElement(etree.Element('dummy'), qn(tag)) if False else etree.Element(qn(tag))
    for k, v in attrs.items():
        el.set(qn('w:' + k), str(v))
    return el

def sub(parent, tag, **attrs):
    el = E(tag, **attrs); parent.append(el); return el

def run(p, text, b=False, i=False, sz=None, font=None, color=None):
    r = sub(p, 'w:r'); rpr = sub(r, 'w:rPr')
    if font:
        sub(rpr, 'w:rFonts', ascii=font, eastAsia=font, hAnsi=font, cs=font)
    if b: sub(rpr, 'w:b'); sub(rpr, 'w:bCs')
    if i: sub(rpr, 'w:i'); sub(rpr, 'w:iCs')
    if color: sub(rpr, 'w:color', val=color)
    if sz: sub(rpr, 'w:sz', val=sz); sub(rpr, 'w:szCs', val=sz)
    t = sub(r, 'w:t'); t.text = text; t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return r

def rich(p, text, **kw):
    """**bold** segments inside text."""
    for k, seg in enumerate(re.split(r'\*\*', text)):
        if seg:
            run(p, seg, b=(k % 2 == 1) or kw.get('b', False), i=kw.get('i', False), sz=kw.get('sz'))

CURRENT = {'before': None}
def put(el):
    if CURRENT['before'] is not None:
        CURRENT['before'].addprevious(el)
    else:
        final_sectpr.addprevious(el)
    return el

BM = {'id': 900}
TOC_ENTRIES = []   # (level, text, bookmark)
def bookmark(p, key):
    BM['id'] += 1
    name = f"_TocF{BM['id']}"
    pPr = p.find(qn('w:pPr'))
    bs = E('w:bookmarkStart', id=BM['id'], name=name); be = E('w:bookmarkEnd', id=BM['id'])
    pPr.addnext(bs); p.append(be)
    return name

def heading(text, level, page_break=False, toc=True):
    p = E('w:p'); pPr = sub(p, 'w:pPr')
    sub(pPr, 'w:pStyle', val='Heading1' if level == 1 else 'Heading2')
    sub(pPr, 'w:keepNext')
    if page_break: sub(pPr, 'w:pageBreakBefore')
    if level == 1:
        sub(pPr, 'w:spacing', after=300)
    else:
        sub(pPr, 'w:spacing', before=300, after=150)
    rpr = sub(pPr, 'w:rPr'); sub(rpr, 'w:color', val='auto')
    run(p, text, b=True, color='auto', sz=30 if level == 1 else None)
    put(p)
    if toc:
        TOC_ENTRIES.append((level, text, bookmark(p, text)))
    return p

def para(text, indent=True, after=200, italic=False, center=False):
    p = E('w:p'); pPr = sub(p, 'w:pPr')
    sub(pPr, 'w:spacing', after=after, line=360, lineRule='auto')
    if indent and not center: sub(pPr, 'w:ind', firstLine=720)
    sub(pPr, 'w:jc', val='center' if center else 'both')
    rich(p, text, i=italic)
    return put(p)

def bullet(text, num=3):
    p = E('w:p'); pPr = sub(p, 'w:pPr')
    sub(pPr, 'w:pStyle', val='ListParagraph')
    numPr = sub(pPr, 'w:numPr'); sub(numPr, 'w:ilvl', val=0); sub(numPr, 'w:numId', val=num)
    sub(pPr, 'w:spacing', after=100, line=360, lineRule='auto'); sub(pPr, 'w:jc', val='both')
    rich(p, text)
    return put(p)

def subhead(text):
    """Bold bullet sub-heading, as used in the midterm (5.2 'Tools Required')."""
    p = E('w:p'); pPr = sub(p, 'w:pPr')
    sub(pPr, 'w:pStyle', val='ListParagraph')
    numPr = sub(pPr, 'w:numPr'); sub(numPr, 'w:ilvl', val=0); sub(numPr, 'w:numId', val=4)
    sub(pPr, 'w:spacing', before=120, after=60, line=360, lineRule='auto'); sub(pPr, 'w:ind', left=360)
    sub(pPr, 'w:keepNext')
    run(p, text, b=True)
    return put(p)

FIGS = []   # (number, caption)
def figure(fname, num, caption, width=6.0):
    p = d.add_paragraph()               # appended before sectPr; move into place
    pe = p._p
    pPr = pe.get_or_add_pPr()
    sub(pPr, 'w:keepNext'); sub(pPr, 'w:spacing', before=100, after=100); sub(pPr, 'w:jc', val='center')
    p.add_run().add_picture(f"{SHOTS}/{fname}", width=Inches(width))
    put(pe)
    c = E('w:p'); cPr = sub(c, 'w:pPr')
    sub(cPr, 'w:spacing', after=300, line=360, lineRule='auto'); sub(cPr, 'w:jc', val='center')
    run(c, f"Figure {num}. ", b=True, i=True, sz=22); run(c, caption, i=True, sz=22)
    put(c)
    FIGS.append((num, caption))

def code(lines):
    t = copy.deepcopy(T_CODE)
    # drop floating position so the table flows with the text
    tblpPr = t.find('.//' + qn('w:tblpPr'))
    if tblpPr is not None: tblpPr.getparent().remove(tblpPr)
    tc = t.find('.//' + qn('w:tc'))
    ps = tc.findall(qn('w:p'))
    tmpl = ps[0]
    for p in ps: tc.remove(p)
    for line in lines.strip('\n').split('\n'):
        p = copy.deepcopy(tmpl)
        for r in p.findall(qn('w:r'))[1:]: p.remove(r)
        r = p.find(qn('w:r'))
        r.find(qn('w:t')).text = line if line else ' '
        rpr = r.find(qn('w:rPr'))
        if rpr is not None:      # 9 pt so ~70 monospace characters fit in the frame
            for tag in ('w:sz', 'w:szCs'):
                el = rpr.find(qn(tag))
                if el is not None: el.set(qn('w:val'), '18')
        r.find(qn('w:t')).set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        tc.append(p)
    put(t)
    sp = E('w:p'); spr = sub(sp, 'w:pPr'); sub(spr, 'w:spacing', after=0)
    put(sp)

def set_cell_text(tc, text, bold=None):
    ps = tc.findall(qn('w:p'))
    for p in ps[1:]: tc.remove(p)
    p = ps[0]
    runs = p.findall(qn('w:r'))
    rpr = copy.deepcopy(runs[0].find(qn('w:rPr'))) if runs and runs[0].find(qn('w:rPr')) is not None else None
    for r in p:
        if r.tag != qn('w:pPr'): p.remove(r)
    for k, seg in enumerate(re.split(r'\*\*', text)):
        if not seg: continue
        r = sub(p, 'w:r')
        if rpr is not None:
            rr = copy.deepcopy(rpr)
            if k % 2 == 1 and rr.find(qn('w:b')) is None:
                rr.insert(0, E('w:bCs')); rr.insert(0, E('w:b'))
            r.append(rr)
        t = sub(r, 'w:t'); t.text = seg; t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

def table(header, rows, widths):
    t = copy.deepcopy(T_DATA)
    _tp = t.find('.//' + qn('w:tblpPr'))
    if _tp is not None: _tp.getparent().remove(_tp)
    trs = t.findall(qn('w:tr'))
    htr, btr = trs[0], trs[1]
    for tr in trs: t.remove(tr)
    t.find(qn('w:tblPr')).find(qn('w:tblW')).set(qn('w:w'), str(sum(widths)))
    grid = t.find(qn('w:tblGrid'))
    for g in list(grid): grid.remove(g)
    for w in widths: sub(grid, 'w:gridCol', w=w)
    def mk(tmpl, cells):
        tr = copy.deepcopy(tmpl)
        tcs = tr.findall(qn('w:tc'))
        for tc in tcs: tr.remove(tc)
        for k, (txt, w) in enumerate(zip(cells, widths)):
            tc = copy.deepcopy(tcs[min(k, len(tcs) - 1)])
            tc.find(qn('w:tcPr')).find(qn('w:tcW')).set(qn('w:w'), str(w))
            set_cell_text(tc, txt)
            tr.append(tc)
        return tr
    t.append(mk(htr, header))
    for r in rows: t.append(mk(btr, r))
    put(t)
    sp = E('w:p'); spr = sub(sp, 'w:pPr'); sub(spr, 'w:spacing', after=120)
    put(sp)

def table_caption(text):
    c = E('w:p'); cPr = sub(c, 'w:pPr')
    sub(cPr, 'w:keepNext'); sub(cPr, 'w:spacing', before=200, after=80); sub(cPr, 'w:jc', val='center')
    run(c, text, b=True, i=True, sz=22)
    put(c)

def page_label(key, default='…'):
    return str(PAGES.get(key, default))

# ================================================================== FRONT MATTER (roman section)
CURRENT['before'] = SECT_BREAK
heading("LIST OF FIGURES", 1, page_break=True)
LOF_ANCHOR = E('w:p'); put(LOF_ANCHOR)          # list filled at the end
heading("LIST OF TABLES", 1, page_break=True)
LOT_ANCHOR = E('w:p'); put(LOT_ANCHOR)
heading("LIST OF ABBREVIATIONS", 1, page_break=True)
para("The abbreviations below are used throughout this report.", indent=False, after=120)
abbr = copy.deepcopy(T_ABBR)
_tp = abbr.find('.//' + qn('w:tblpPr'))
if _tp is not None: _tp.getparent().remove(_tp)
ab_rows = abbr.findall(qn('w:tr'))
tmpl_row = ab_rows[1]
for tr in ab_rows[1:]: abbr.remove(tr)
for a, m in [
    ("AES-GCM", "Advanced Encryption Standard in Galois/Counter Mode"),
    ("API", "Application Programming Interface"),
    ("CLI", "Command-Line Interface"),
    ("CSP", "Content Security Policy"),
    ("CSPRNG", "Cryptographically Secure Pseudo-Random Number Generator"),
    ("CSRF", "Cross-Site Request Forgery"),
    ("DER", "Distinguished Encoding Rules"),
    ("ECC", "Elliptic Curve Cryptography"),
    ("ECDSA", "Elliptic Curve Digital Signature Algorithm"),
    ("GUI", "Graphical User Interface"),
    ("HMAC", "Hash-based Message Authentication Code"),
    ("HMAC-DRBG", "HMAC-based Deterministic Random Bit Generator"),
    ("HSM", "Hardware Security Module"),
    ("KDF", "Key Derivation Function"),
    ("MGF1", "Mask Generation Function 1"),
    ("PBKDF2", "Password-Based Key Derivation Function 2"),
    ("PDF", "Portable Document Format"),
    ("PEM", "Privacy-Enhanced Mail (key file format)"),
    ("PKI", "Public Key Infrastructure"),
    ("PoP", "Proof-of-Possession (of a private key)"),
    ("PSS", "Probabilistic Signature Scheme"),
    ("RFC", "Request for Comments"),
    ("RSA", "Rivest–Shamir–Adleman (algorithm)"),
    ("SHA", "Secure Hash Algorithm"),
    ("TSA", "Time-Stamping Authority"),
    ("XFF", "X-Forwarded-For (HTTP header)"),
]:
    tr = copy.deepcopy(tmpl_row)
    tcs = tr.findall(qn('w:tc'))
    set_cell_text(tcs[0], a); set_cell_text(tcs[1], m)
    abbr.append(tr)
put(abbr)

heading("ABSTRACT", 1, page_break=True)
para("This report presents the practical phase of our project on digital signatures. Our midterm report analysed RSA and "
     "ECDSA, the role of hash functions and non-repudiation, and argued that real-world breaks come from implementation "
     "mistakes rather than from the mathematics. For the final phase we built SecureSign Cloud, a multi-user web platform "
     "that signs and verifies PDF documents with RSA-PSS or ECDSA P-256 and SHA-256. Each user generates a key pair in the browser; "
     "the private key is encrypted with PBKDF2 and AES-256-GCM and never leaves the device, and a public key is accepted "
     "only after a challenge-response proof-of-possession. The server re-verifies every signature, isolates documents "
     "between sender and recipient, and protects accounts with Argon2id, CSRF tokens, rate limiting and a strict Content "
     "Security Policy. To guarantee non-repudiation, every signing, delivery and key event becomes a server-signed, "
     "timestamped receipt in a SHA-256 hash-chained evidence log. Inside the same application we built a Security Lab "
     "that demonstrates four attacks on badly "
     "implemented signatures and their patches. The main attack is ECDSA nonce reuse: from two public signed invoice "
     "PDFs the attacker recovers the private key and forges a 1,000,000 USD invoice that both the cryptography library "
     "and OpenSSL accept. RFC 6979 deterministic nonces defeat the same attack code. The lab also shows textbook RSA "
     "forgery versus RSA-PSS, key substitution versus proof-of-possession, and repudiation and log tampering versus the "
     "evidence chain. While integrating the platform we found "
     "and fixed three security bugs. All results are covered by 37 automated tests, and both success criteria from the "
     "midterm plan were met.")
p = para("Keywords: digital signature, RSA-PSS, ECDSA, nonce reuse, RFC 6979, proof-of-possession, timestamped receipt, hash chain, non-repudiation.",
         indent=False, italic=True)

# ================================================================== MAIN BODY (arabic section)
CURRENT['before'] = None

# ---------------- CHAPTER 1
heading("CHAPTER 1. INTRODUCTION AND PROJECT METADATA", 1)
heading("1.1 Project Metadata", 2)
table_caption("Table 1.1. Project metadata")
table(["Item", "Details"], [
    ["Project topic", "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation (SecureSign Cloud PDF signing platform with signed receipts, ECDSA nonce-reuse attack and RFC 6979 defense)"],
    ["Course", "Introduction to Information Security, Faculty of Information Technology, Ton Duc Thang University"],
    ["Instructor", "Ph.D. Huynh Ngoc Tu"],
    ["Group", "N05_G05"],
    ["Group members (names and IDs)", "Trieu Ngoc Van Anh (524H0005); Duong Tran Quoc Khanh (523H0040); Nguyen Vo Thanh Tu (523H0189)"],
    ["Repository link", "https://github.com/duongtranquockhanhwork/final-BMTT"],
], [2600, 6187])
heading("1.2 Executive Summary", 2)
para("We built SecureSign Cloud, a multi-user web application for signing PDF documents, and a Security Lab inside it. "
     "SecureSign is the correct use of digital signatures: RSA-PSS or ECDSA P-256 keys are created and stored encrypted "
     "in the user's browser, the server re-verifies every signature and only accepts a public key after a "
     "proof-of-possession challenge, and every signing or delivery yields a server-signed, timestamped receipt in a "
     "hash-chained evidence log, so a signer cannot later deny it. The main attack we demonstrate is ECDSA nonce reuse: "
     "an invoice-signing service reuses the nonce k, an attacker who only sees two public signed PDFs recovers the "
     "private key in milliseconds, and a forged 1,000,000 USD invoice is accepted by the cryptography library and by "
     "OpenSSL. We then patch the signer with RFC 6979 and show that the unchanged attack code fails. Three further lab "
     "scenes show textbook RSA forgery versus RSA-PSS, key substitution versus proof-of-possession, and repudiation and "
     "log tampering versus the evidence chain.")
heading("1.3 Relation to the Midterm Plan", 2)
para("Section 5.2 of our midterm report defined two success criteria. (1) The correct-use demo succeeds if valid signatures "
     "verify and any tampered message is rejected for both RSA and ECDSA. (2) The attack demo succeeds if the ECDSA private "
     "key is recovered purely from two signatures sharing a reused nonce, and a signature forged with that key is accepted. "
     "Both criteria are met (Chapter 4), now on real PDF documents rather than short strings. We went beyond the plan "
     "with a complete signing platform that supports both RSA and ECC, signed receipts for non-repudiation, the RFC 6979 "
     "patch, three extra attack/defense scenes and 37 automated tests.")
para("Two tools changed from the plan. The ecdsa package was replaced by our own small P-256 module (ecc_core.py), because "
     "audited libraries deliberately never let the caller choose k, and we need that to reproduce the bug; correctness is "
     "proven by cross-checking against the cryptography library. Jupyter Notebook was replaced by the SecureSign web "
     "application and its Security Lab page, which is easier to present live and is closer to a real deployment.")
heading("1.4 Report Structure", 2)
para("Chapter 2 describes the lab environment needed to reproduce the demonstration. Chapter 3 explains the architecture, "
     "the key code snippets and the algorithms. Chapter 4 walks through the live demonstration step by step with "
     "screenshots. Chapter 5 presents the patches, the security fixes we made while integrating the platform, and how an "
     "attacker might still try to bypass the defenses. Chapter 6 concludes with the challenges, limitations and possible "
     "improvements.")

# ---------------- CHAPTER 2
heading("CHAPTER 2. LAB ENVIRONMENT AND TOOLS SETUP", 1, page_break=True)
heading("2.1 Hardware and Virtual Machines", 2)
para("Any x86-64 or Apple Silicon laptop or PC is sufficient. We developed and ran the demonstration on macOS and Windows "
     "10 Pro 64-bit. No virtual machine, special hardware or second host is needed: two browser windows (or one normal and "
     "one private window) are enough to play Alice and Bob. The server uses less than 150 MB of RAM, and every lab step "
     "finishes in under one second (RSA key generation takes about 0.2 seconds, ECDSA key generation a few milliseconds).")
heading("2.2 Software and Libraries", 2)
table_caption("Table 2.1. Software and libraries")
table(["Component", "Version", "Purpose"], [
    ["Python", "3.11.9 (3.11+ required)", "Runtime for the server, the lab, the console demos and the tests"],
    ["FastAPI, Uvicorn", "≥ 0.115 / ≥ 0.30", "Web API and ASGI server"],
    ["SQLAlchemy + SQLite / PostgreSQL", "≥ 2.0", "Users, sessions, public keys, documents, audit log and evidence chain (SQLite locally, PostgreSQL in deployment)"],
    ["cryptography", "≥ 44 (tested 46 and 50)", "Server-side RSA-PSS and ECDSA verification, key parsing, receipt signing; version 44+ is needed for deterministic_signing in the RFC 6979 cross-check"],
    ["argon2-cffi", "≥ 23.1", "Argon2id password hashing"],
    ["Web Crypto API", "Any modern browser (Chrome, Edge, Firefox, Safari)", "RSA-PSS and ECDSA P-256 key generation and signing, PBKDF2 and AES-256-GCM private-key encryption in the browser"],
    ["pytest, httpx", "≥ 8.3 / ≥ 0.27", "Automated test suite"],
    ["OpenSSL / LibreSSL CLI", "3.x / 3.3 (optional)", "Independent verification of the forged PDF, ECDSA .sig files and openssl_demo.sh"],
    ["Docker, Caddy (optional)", "Compose v2, Caddy 2", "Deployment with PostgreSQL and automatic HTTPS (not needed for the demo)"],
], [2300, 2400, 4087])
heading("2.3 Network Configuration", 2)
para("For the demonstration the server binds only to 127.0.0.1 on port 8000, so it is not reachable from other hosts. Web "
     "Crypto requires a secure context, which browsers grant to localhost; any other address must use HTTPS. Locally the "
     "app uses SQLite in source/storage/ and does not require email verification. For an Internet deployment, "
     "docker-compose.yml runs the app behind Caddy, which obtains a TLS certificate, overwrites the X-Forwarded-For header "
     "and forwards to the app; PostgreSQL is only reachable on the internal Docker network. The \"public channel\" in the "
     "Security Lab is simulated in-process, and the forged invoice, its signature and the public key can be downloaded so "
     "that anyone can re-check the forgery offline.")
heading("2.4 Reproduction Steps and Project Structure", 2)
code("""python -m venv .venv
.venv\\Scripts\\activate     # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -v                # 37 automated checks
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# web app:      http://127.0.0.1:8000   (demo accounts: Table 2.3)
#   Security Lab:  http://127.0.0.1:8000/lab  (after signing in)
python demos/run_all.py --pause    # console version of scenes 1-4""")
table_caption("Table 2.2. Source files and their roles")
table(["File", "Role"], [
    ["backend/app/main.py", "FastAPI application: registration and login, key registry, signing record, verification, document exchange, administration, security middleware"],
    ["backend/app/crypto_service.py", "verify_signature() for RSA-PSS and ECDSA P-256, verify_proof_of_possession(), public-key policy and fingerprints"],
    ["backend/app/evidence.py", "Server-signed receipts, SHA-256 hash-chained evidence log, chain and receipt verification"],
    ["backend/app/security.py", "Argon2id password hashing, hashed session tokens, double-submit CSRF check, admin role check"],
    ["backend/app/database.py", "SQLAlchemy models (including the evidence entries) and admin bootstrap"],
    ["backend/app/lab.py", "Security Lab API: six scenes, state kept per user"],
    ["backend/lab/ecc_core.py, attack.py", "Educational P-256 ECDSA with explicit nonce, RFC 6979; nonce-reuse detection and key recovery"],
    ["backend/lab/pdf_tools.py", "Small deterministic PDF builder, so the lab signs real PDF bytes"],
    ["frontend/index.html, app.js", "SecureSign web app; key generation, encryption and signing in the browser"],
    ["frontend/lab/", "Security Lab story page (English/Vietnamese)"],
    ["demos/", "Console demos 1–4, run_all.py, openssl_demo.sh and verify_receipt.py (offline receipt check)"],
    ["backend/app/demo_seed.py, demo_data/", "Demo accounts created at start-up in development, their encrypted key files and sample PDFs"],
    ["tests/", "pytest suite (RSA and ECDSA, multi-user isolation, receipts and evidence chain, lab attacks and patches, security fixes, demo accounts)"],
], [3000, 5787])
para("To make the demonstration reproducible without registering, the server creates the demo accounts in Table 2.3 when "
     "it runs in development mode. Alice already owns a registered RSA-PSS 2048 key and Bob an ECDSA P-256 key, and their encrypted private "
     "keys are shipped in demo_data/ in exactly the format the browser produces (key password DemoKey@2026), together with "
     "an original and a tampered sample contract PDF. These credentials are public by design: the server refuses to start "
     "if demo accounts are enabled with APP_ENV=production.")
table_caption("Table 2.3. Demo accounts (development mode only)")
table(["Role", "Email", "Password", "Key file in demo_data/"], [
    ["Admin", "admin@securesign-demo.com", "Admin@Demo2026", "–"],
    ["Signer", "alice@securesign-demo.com", "Alice@Demo2026", "alice.key.json (RSA)"],
    ["Recipient", "bob@securesign-demo.com", "Bob@Demo2026", "bob.key.json (ECDSA)"],
    ["Outsider", "charlie@securesign-demo.com", "Charlie@Demo2026", "– (no access to their documents)"],
], [1400, 3000, 2250, 2137])

# ---------------- CHAPTER 3
heading("CHAPTER 3. CORE IMPLEMENTATION AND CODE ANALYSIS", 1, page_break=True)
heading("3.1 Architecture and Flow Logic", 2)
para("SecureSign has three tiers (Figure 3.1a). The browser performs every operation that needs the private key. The "
     "FastAPI backend stores only public keys, enforces access control and re-checks every signature with the "
     "cryptography library before it records or forwards anything, and writes every security-relevant event to a "
     "server-signed, hash-chained evidence log. The database and file storage hold accounts, sessions, public keys, "
     "documents, the audit log and the evidence chain.")
para("Flow of the signing workflow: (1) Alice registers; her password is hashed with Argon2id and she receives an HttpOnly "
     "session cookie and a CSRF token. (2) Her browser generates an RSA-2048 or ECDSA P-256 key pair, encrypts the private key with a "
     "password and offers it as a .key.json file. (3) To register the public key, the server issues a one-time random "
     "challenge; the browser signs it, and the server links the key to Alice only if the proof verifies. (4) To sign, the "
     "browser decrypts the key locally, signs the PDF bytes with RSA-PSS or ECDSA (the algorithm is fixed by the registered "
     "key, never by the client) and produces a detached .sig file; the server re-verifies it and returns a signed receipt. "
     "(5) When Alice sends the PDF and .sig to Bob, the server verifies them against Alice's registered key, stores them "
     "in Bob's inbox and issues a delivery receipt; only the sender and the recipient can download or verify the document "
     "and its receipts. (6) Bob verifies the document (which is also recorded) and can mark Alice's key as trusted after "
     "comparing its fingerprint through another channel. (7) Any receipt can later be checked online or offline, and the "
     "administrator can check the integrity of the whole chain.")
para("Flow of the attack (Security Lab, Figure 3.1b): (1) a vulnerable invoice service draws its ECDSA nonce k once at "
     "start-up; (2) it signs two invoice PDFs, and both signatures carry the same r because r = (k·G).x; (3) the attacker "
     "groups the public signatures by r, finds the collision and solves two linear equations for k and then d; (4) the "
     "recovered d is checked against the public key (d·G = Q); (5) d is imported into a normal cryptography private-key "
     "object to sign a malicious invoice PDF; (6) the relying party verifies it with the real Q and accepts it. The fixed "
     "scene swaps only the nonce source for RFC 6979 and re-runs the same pipeline unchanged, so any difference in the "
     "outcome is caused by the patch alone.")
figure("fig00_architecture.png", "3.1", "Architecture. (a) SecureSign production signing workflow. (b) Security Lab nonce-reuse attack flow and the RFC 6979 patch.")
heading("3.2 Demonstration GUI", 2)
para("The SecureSign web app (Vietnamese interface) has a dashboard, key management, signing, verification, document "
     "sending, an inbox, a personal audit history with a receipt for each recorded event and, for administrators, user "
     "management and the evidence-log integrity check (Figures 3.2 and 3.3). Administrators can suspend accounts and "
     "change roles, but cannot read users' private documents, and the last active administrator cannot be removed. "
     "Every file picker shows the chosen file with its size and a remove (✕ Gỡ) button and accepts drag and drop.")
figure("fig08_admin.png", "3.2", "Administrator view: accounts, roles, status, keys and documents per user.", 6.0)
figure("fig09_history.png", "3.3", "Personal audit trail with a downloadable server-signed receipt for each recorded event.", 6.0)
para("The Security Lab (/lab) tells the demonstration as a story so that a non-specialist audience can follow it. Four "
     "columns show the actors (signer, public channel, attacker Eve, verifier). The presenter presses one button (or the → "
     "key) per step; the step calls the real lab API, new cards appear in the column of the actor who acted, and a "
     "plain-language explanation is shown at the top. Long numbers are displayed as short coloured fingerprints, so equal "
     "values have equal colours: the audience can see at a glance that two signatures share the same r, or that the key "
     "computed by Eve is identical to the service's private key. The page switches between English and Vietnamese, and "
     "Show math reveals the equations and full values. Unlike our midterm prototype, the lab is part of the secured "
     "application: it requires a signed-in session and the CSRF token, keeps its keys separately for each user, signs "
     "real PDF bytes, and uses SecureSign's own verify_signature() and verify_proof_of_possession() where they apply.")
table_caption("Table 3.1. Scenes of the Security Lab")
table(["Scene", "Steps (one click each)"], [
    ["1 · How it works", "Alice creates her keys → signs the contract PDF → Bob verifies (VALID) → Eve changes 1,000 to 9,000 USD (INVALID) → Eve signs with her own key (INVALID)"],
    ["2 · The attack", "Service starts (bug: k reused) → signs invoice PDF #1001 → #1002 (same r) → Eve computes the private key (matches) → Eve's 1,000,000 USD invoice is accepted by the bank"],
    ["3 · The fix", "Same five steps with RFC 6979: different r → wrong key → forgery rejected; plus a byte-for-byte cross-check with the cryptography library"],
    ["4 · RSA padding", "Alice signs 100 and 50 with textbook RSA → Eve multiplies the signatures, 5,000 is accepted → the same trick against RSA-PSS is rejected"],
    ["5 · Key registry", "Alice registers her key with proof-of-possession → Eve registers Alice's public key in a registry without proof (Alice's PDF now shows \"signed by Eve\") → Eve tries the same against SecureSign (rejected)"],
    ["6 · Non-repudiation", "Alice signs and sends (three chained receipts) → Alice denies with a later-dated receipt signed by her own key (rejected) → an insider edits entry #2 (detected) → the insider recomputes every hash (still detected: no server signature)"],
], [2000, 6787])
heading("3.3 Key Code Snippets and Explanation", 2)
subhead("Snippet 1: Key generation, private-key protection and signing in the browser (frontend/app.js)")
code('''const ALGORITHMS = {
  "RSA-PSS": {
    generate: {name: "RSA-PSS", modulusLength: 2048,
               publicExponent: new Uint8Array([1, 0, 1]),
               hash: "SHA-256"},
    signParams: {name: "RSA-PSS", saltLength: 32}},
  "ECDSA-P256": {
    generate: {name: "ECDSA", namedCurve: "P-256"},
    signParams: {name: "ECDSA", hash: "SHA-256"}}};

const pair = await crypto.subtle.generateKey(
    ALGORITHMS[alg].generate, true, ["sign", "verify"]);
const pkcs8 = await crypto.subtle.exportKey("pkcs8", pair.privateKey);
const salt = crypto.getRandomValues(new Uint8Array(16));
const iv = crypto.getRandomValues(new Uint8Array(12));
const material = await crypto.subtle.importKey("raw",
    new TextEncoder().encode(password), "PBKDF2", false,
    ["deriveKey"]);
const aesKey = await crypto.subtle.deriveKey(
    {name: "PBKDF2", salt, iterations: 310000, hash: "SHA-256"},
    material, {name: "AES-GCM", length: 256}, false, ["encrypt"]);
const encrypted = await crypto.subtle.encrypt(   // only this is saved
    {name: "AES-GCM", iv}, aesKey, pkcs8);

async function signAndCheck(alg, privateKey, publicKey, data) {
  const p = ALGORITHMS[alg].signParams;
  const raw = new Uint8Array(
      await crypto.subtle.sign(p, privateKey, data));
  if (!(await crypto.subtle.verify(p, publicKey, raw, data)))
    throw new Error("Private Key and Public Key do not match.");
  // ECDSA: Web Crypto returns r||s; server and OpenSSL expect DER
  return alg === "ECDSA-P256" ? ecdsaRawToDer(raw) : raw;
}''')
para("Explanation: the key pair is created by the browser's Web Crypto API, which uses the operating system's CSPRNG, "
     "for either RSA-PSS 2048 or ECDSA P-256; both use SHA-256, so the same PDF digest is signed in both cases. The "
     "private key is exported only to be encrypted immediately: PBKDF2-HMAC-SHA256 with a random 16-byte salt and "
     "310,000 iterations turns the user's password into a 256-bit AES key, which makes offline password guessing slow, "
     "and AES-256-GCM encrypts the key and adds an authentication tag, so a wrong password or a modified key file fails "
     "to decrypt instead of producing a wrong key. Only the encrypted bundle is saved, and nothing secret is sent to the "
     "server. signAndCheck() signs the PDF bytes (RSA-PSS with a 32-byte salt, or ECDSA with a fresh random nonce from the "
     "browser), verifies the new signature with the public key before it leaves the browser, and converts ECDSA "
     "signatures from the raw r||s form that Web Crypto returns to the DER form used by the server and OpenSSL. An ECDSA "
     "signature is about 72 bytes, compared with 256 bytes for RSA-2048.")
subhead("Snippet 2: Server-side checks: proof-of-possession and re-verification (crypto_service.py, main.py)")
code('''def verify_proof_of_possession(public_key, challenge, proof_b64):
    try:
        proof = base64.b64decode(proof_b64, validate=True)
        # RSA-PSS or ECDSA, chosen by the type of the registered key
        verify_detached_signature(challenge.encode(), proof,
                                  public_key)
        return True
    except (ValueError, InvalidSignature):
        return False

# POST /api/keys  (register a public key)
challenge = db.scalar(select(KeyChallenge).where(
    KeyChallenge.id == payload.challenge_id,
    KeyChallenge.user_id == user.id, KeyChallenge.used_at.is_(None),
    KeyChallenge.expires_at > utc_now()))
if not challenge:
    raise HTTPException(400, "Challenge invalid, expired or used.")
if not verify_proof_of_possession(public_key, challenge.challenge_value,
                                  payload.proof_signature):
    raise HTTPException(400, "Could not prove ownership of the key.")
challenge.used_at = utc_now()

# POST /api/documents/send
result = verify_signature(pdf_bytes, signature_bytes,
                          key.public_key_pem.encode())
if not result["valid"]:
    raise HTTPException(400, "Signature does not match PDF and key.")''')
para("Explanation: a public key is public, so anyone can copy it from the directory. The server therefore creates a "
     "random 32-byte challenge bound to the current user, valid for 5 minutes and usable once, and links a key to an "
     "account only if the user can sign that challenge with the matching private key. This blocks the key-substitution "
     "attack of lab scene 5, and the single-use challenge prevents replaying an old proof. Fingerprints are also unique, so "
     "a key can belong to only one account. The server never trusts the browser's claim that a signature is valid: before "
     "a signing event is recorded or a document is delivered, verify_signature() checks the PDF and .sig against the "
     "sender's registered key with the cryptography library.")
subhead("Snippet 3: The vulnerable signer and the private-key recovery (lab.py, attack.py)")
code('''def start(self, req):            # vulnerable invoice-signing service
    self.d, self.Q = E.generate_keypair()
    self._k = secrets.randbelow(E.N - 1) + 1  # only ONCE: the BUG

def sign(self, req):
    pdf = make_pdf(_text(req), title="SecureSign Invoice")
    k = self._k                              # same k for every PDF
    r, s = E.ecdsa_sign(pdf, self.d, k)   # s = k^-1(H(pdf)+r*d) mod n

def recover_nonce(m1, sig1, m2, sig2):    # attacker: public data
    (r1, s1), (r2, s2) = sig1, sig2
    if r1 != r2:
        raise ValueError("r values differ: the nonce was NOT reused")
    h1, h2 = hash_to_int(m1), hash_to_int(m2)
    return (h1 - h2) * inv(s1 - s2, N) % N

def recover_private_key(m1, sig1, k):
    r, s1 = sig1
    return (s1 * k - hash_to_int(m1)) * inv(r, N) % N''')
para("Explanation: the private key d comes from a CSPRNG, so the key itself is strong. The bug is that the nonce k is drawn "
     "only once and stored. Every call to sign() therefore computes R = k·G with the same k, so the public value r = R.x "
     "mod n is identical for every PDF, which tells anyone that k was reused. The signing equation is the standard ECDSA "
     "formula (FIPS 186-5) and every signature verifies, which is why the bug goes unnoticed in normal testing. The attacker "
     "subtracts the two equations: s1 − s2 = k⁻¹(h1 − h2) cancels r·d, so k = (h1 − h2)(s1 − s2)⁻¹ mod n, and then the first "
     "equation has a single unknown and gives d = (s1·k − h1)·r⁻¹ mod n. The guard r1 ≠ r2 → ValueError is what makes the "
     "attack fail against the patched signer. This is the same class of bug as the 2010 Sony PlayStation 3 key leak.")
heading("3.4 Algorithms and Cryptography Used", 2)
table_caption("Table 3.2. Algorithms used and rationale")
table(["Algorithm", "Where used", "Why we chose it"], [
    ["RSASSA-PSS, RSA-2048, e = 65537, SHA-256, MGF1-SHA256, 32-byte salt (RFC 8017)", "SecureSign signing and verification (user choice), proof-of-possession, lab scenes 1, 4, 5, 6", "Provably secure RSA signature encoding, supported natively by Web Crypto and by the cryptography library. The random salt and hash-based padding remove the multiplicative structure of textbook RSA. The server rejects keys below 2048 or above 4096 bits and any exponent other than 65537."],
    ["SHA-256 (FIPS 180-4)", "PDF digests, key fingerprints, token hashes", "Collision-resistant 256-bit digest; MD5 and SHA-1 were rejected because practical collisions exist. A one-character change in the PDF changes about half of the 256 bits."],
    ["PBKDF2-HMAC-SHA256 (310,000 iterations) + AES-256-GCM", "Encrypted private-key file in the browser", "The only password-based KDF and authenticated cipher available in every browser's Web Crypto API. GCM detects any modification of the key file."],
    ["Argon2id (t = 3, 64 MiB, p = 2)", "Account passwords on the server", "Memory-hard hash recommended by OWASP; makes GPU password cracking expensive if the database leaks."],
    ["ECDSA over NIST P-256 with SHA-256 (DER)", "SecureSign signing and verification (user choice), lab scenes 1–3, console demos", "The most widely deployed ECC signature: about 128-bit security with a 256-bit key and a ~72-byte signature (RSA needs about 3072 bits for the same level). Its dependence on a secret per-signature nonce is exactly the weakness we demonstrate; the browser's implementation draws a fresh random nonce for every signature."],
    ["ECDSA P-256 server receipts + SHA-256 hash chain", "Evidence log, receipts, lab scene 6", "The server signs each receipt (time, PDF digest, signer key) so it cannot be forged or back-dated; linking each entry to the SHA-256 of the previous one makes deletions, insertions and edits detectable. Small signatures keep the log compact."],
    ["RFC 6979 deterministic nonce (HMAC-DRBG / HMAC-SHA256)", "Lab scene 3 (the patch)", "k = f(d, H(m)) is unique per message and unpredictable without d, and needs no runtime RNG, which also protects against broken or low-entropy RNGs."],
    ["Textbook RSA s = m^d mod n", "Lab scene 4 only (insecure baseline)", "Shown only as a counter-example to explain why padding is mandatory."],
], [2400, 2000, 4387])
para("Implementation choices: SecureSign never implements cryptography itself. The browser uses Web Crypto and the server "
     "uses the cryptography library, which wraps OpenSSL. Our own P-256 code exists only in the Security Lab, because no "
     "audited library lets the caller choose k. To make sure this educational code is correct, (a) our public keys match "
     "the library's for the same d, (b) our signatures verify under the library, and (c) our RFC 6979 output matches the "
     "official test vector (RFC 6979 A.2.5) and is byte-identical to cryptography's deterministic_signing=True.")

# ---------------- CHAPTER 4
heading("CHAPTER 4. STEP-BY-STEP DEMONSTRATION WALKTHROUGH", 1, page_break=True)
para("The live demonstration runs on one laptop: start the server, open SecureSign in two browser windows for Alice and "
     "Bob, then open the Security Lab and press → once per step. Every value on screen is computed live. Table 4.1 maps the "
     "three steps required by the course template to the demonstration.")
table_caption("Table 4.1. Mapping of the demonstration steps")
table(["Template step", "SecureSign / Security Lab", "Console"], [
    ["Step 1: Initialization", "Tests; SecureSign workflow (register, key + proof-of-possession, sign, send, verify, tampered copy); lab scene 1; lab scene 2 steps 1–3 (service starts, two invoice PDFs with the same r)", "pytest -v, demo1, start of demo2"],
    ["Step 2: Execution / The attack", "Lab scene 2 step 4: Eve computes the private key", "demo2 steps 3–4"],
    ["Step 3: Verification / The result", "Lab scene 2 step 5: forged invoice accepted; re-checked with OpenSSL", "demo2 steps 5–6, openssl dgst"],
    ["Patch (Chapter 5)", "Lab scene 3 (RFC 6979), scene 4 (RSA-PSS), scene 5 (proof-of-possession), scene 6 and receipts (non-repudiation); security fixes", "demo3, demo4, verify_receipt.py, test_hardening.py"],
], [2300, 4300, 2187])
heading("4.1 Step 1: Initialization", 2)
para("Description: install the dependencies and run the test suite to prove that the system is correct before the demo "
     "(Figure 4.1: 37 of 37 tests pass, including the official RFC 6979 test vector, multi-user isolation and every lab "
     "scene). Start the server; for the live demo we register Alice and Bob from scratch to show the full key set-up (the demo accounts of Table 2.3 skip this) (Figure 4.2). Alice creates an RSA-2048 key pair "
     "in the browser, downloads the encrypted private key and registers the public key; the success message confirms that "
     "the proof-of-possession was verified (Figure 4.3). She signs the contract PDF: the browser decrypts the key locally, "
     "signs, and the server re-verifies the signature before recording it and returns a server-signed, timestamped receipt "
     "(Figure 4.4). She sends the PDF and the .sig to Bob (Figure 4.5).")
figure("fig01_tests.png", "4.1", "37/37 automated tests pass (RSA and ECDSA, multi-user isolation, receipts and evidence chain, Security Lab, security fixes, demo accounts).", 6.0)
figure("fig02_dashboard.png", "4.2", "SecureSign dashboard after registration.", 6.0)
figure("fig03_keys.png", "4.3", "Key pair generated in the browser; the public key is registered after a successful proof-of-possession.", 6.0)
figure("fig04_sign.png", "4.4", "PDF signed with RSA-PSS in the browser; digest, key fingerprint, algorithm, signature size and the server receipt number.", 6.0)
figure("fig05_send.png", "4.5", "Alice sends the signed PDF to Bob; the server verifies the signature before delivery.", 6.0)
para("Bob compares the fingerprint of Alice's key and marks it as trusted, then verifies the document in his inbox: the "
     "signature is valid and the key is trusted (Figure 4.6). He then verifies a copy in which 1,000 USD was changed to "
     "9,000 USD with the same .sig: the signature is rejected (Figure 4.7). Lab scene 1 shows the same integrity, "
     "authentication and non-repudiation checks for both RSA-PSS and ECDSA (Figure 4.8). Finally, start lab scene 2: the "
     "vulnerable invoice service generates its key pair (the private key is blurred, so the audience can compare it later), "
     "signs invoice PDFs #1001 and #1002, and both signatures verify while sharing the same r value (Figure 4.10, left).")
figure("fig06_inbox_verified.png", "4.6", "Bob's inbox: the received PDF is verified as valid and signed with a key he trusts.", 6.0)
figure("fig07_verify_tampered.png", "4.7", "A tampered copy (1,000 → 9,000 USD) with the original signature is rejected.", 6.0)
figure("fig10_lab_correct.png", "4.8", "Lab scene 1: genuine contract PDF accepted; tampered PDF and Eve's own signature rejected.", 6.0)
heading("4.2 Step 2: Execution / The Attack", 2)
para("Description: the attacker scans the public signatures and finds two with the same r, which proves that k was reused. "
     "Applying k = (h1 − h2)/(s1 − s2) mod n and d = (s1·k − h1)/r mod n recovers the 256-bit private key in milliseconds. "
     "It is identical to the service's hidden d, and d·G equals the published public key Q (Figure 4.9). In the lab this is "
     "scene 2, step 4: the key computed by Eve appears with the same colour fingerprint as the service's private key, "
     "which is then revealed for comparison; Show math displays both equations and the full values.")
figure("fig11_demo2_attack.png", "4.9", "Console: nonce and private key recovered from two public signatures.", 5.6)
heading("4.3 Step 3: Verification / The Result", 2)
para("Description: Eve creates the PDF \"Invoice #6666: pay 1,000,000 USD to Eve's account\" and signs it with the stolen "
     "key. The bank verifies it with the service's real public key using cryptography's ECDSA verify(), and the result is "
     "VALID (Figure 4.10). To show that this is not a quirk of our own code, we download the forged PDF, its signature and "
     "the public key from the lab and check them with OpenSSL: \"Verified OK\". Changing one amount in the forged PDF makes "
     "OpenSSL fail, so the forgery is a genuine signature on exactly that document (Figure 4.11). The forged invoice cannot "
     "be told apart from a real one, so integrity, authentication and non-repudiation are all broken. This meets the attack "
     "success criterion defined in Section 5.2 of our midterm report.")
figure("fig12_lab_attack.png", "4.10", "Lab scene 2 after all five steps: identical r values, private key recovered, forged 1,000,000 USD invoice accepted.", 6.0)
figure("fig13_openssl_forgery.png", "4.11", "Independent check: OpenSSL accepts the forged invoice PDF and rejects an edited copy.", 6.0)

# ---------------- CHAPTER 5
heading("CHAPTER 5. VULNERABILITY PATCH AND DEFENSE MECHANISM", 1, page_break=True)
heading("5.1 The Patch: RFC 6979 Deterministic Nonces", 2)
para("The root cause is a nonce that is not unique per message. We replaced it with RFC 6979 deterministic nonce "
     "generation, the same approach used by libsecp256k1 (Bitcoin), Ed25519 by design, and the cryptography library's "
     "deterministic_signing option. Only the nonce source changes. The key, curve, hash and signing equation stay the same.")
code('''def sign(self, req):                        # patched service
    pdf = make_pdf(_text(req), title="SecureSign Invoice")
    k = E.rfc6979_nonce(self.d, pdf)      # FIX: k = f(d, H(pdf))
    r, s = E.ecdsa_sign(pdf, self.d, k)

def rfc6979_nonce(d: int, message: bytes) -> int:
    h1 = hashlib.sha256(message).digest()
    V = b"\\x01" * 32
    K = b"\\x00" * 32
    seed = _int2octets(d) + _bits2octets(h1)
    K = hmac.new(K, V + b"\\x00" + seed, hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    K = hmac.new(K, V + b"\\x01" + seed, hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    while True:
        V = hmac.new(K, V, hashlib.sha256).digest()
        k = int.from_bytes(V, "big")
        if 1 <= k < N:
            return k
        K = hmac.new(K, V + b"\\x00", hashlib.sha256).digest()
        V = hmac.new(K, V, hashlib.sha256).digest()''')
para("Explanation: K and V are the state of an HMAC-DRBG seeded with the private key d and the PDF hash h1. Because "
     "HMAC-SHA256 is a pseudo-random function keyed by secret material, k is (1) the same only when both d and the PDF are "
     "the same, in which case the signature is also the same and nothing new leaks, (2) different and unrelated for any "
     "different PDF, and (3) unpredictable to anyone who does not know d. The rejection loop keeps 1 ≤ k < n. No runtime "
     "random number generator is involved, so a broken, seeded or low-entropy RNG can no longer leak the key.")
heading("5.2 Verification of the Patch", 2)
para("Re-running the unchanged attack pipeline against the patched signer gives: r1 ≠ r2, so recover_nonce() refuses to "
     "run. Forcing the formulas anyway yields a guess d′ with d′·G ≠ Q. The forgery made with d′ is REJECTED by the bank. "
     "Our signature is also byte-identical to the one produced by cryptography with deterministic_signing=True, which "
     "confirms the patch matches the standard (Figures 5.1 and 5.2).")
figure("fig14_demo3_defense.png", "5.1", "Console: the same attack fails against the RFC 6979 signer.", 5.6)
figure("fig15_lab_defense.png", "5.2", "Lab scene 3: different r values, wrong key, forgery rejected, output byte-identical to the audited library.", 6.0)
heading("5.3 Related Defenses: RSA Padding and Proof-of-Possession", 2)
para("Textbook RSA signatures are multiplicative: from sign(100) and sign(50) the attacker computes sign(5000) = s1·s2 mod n "
     "without the private key, and it verifies. With RSA-PSS, which SecureSign uses exclusively, the same product is "
     "rejected because each signature covers a randomly salted, hashed encoding rather than the raw number (Figure 5.3).")
figure("fig16_lab_rsa.png", "5.3", "Lab scene 4: the multiplied textbook RSA signature is accepted for 5,000; the same trick is rejected by RSA-PSS.", 6.0)
para("A signature only proves that the holder of a given public key signed; the key registry decides who that holder is. "
     "In a registry that stores (public key → owner) without any check, Eve can upload Alice's public key under her own "
     "account. Alice's PDFs still verify mathematically, but now appear as \"signed by Eve\", so Eve can claim Alice's "
     "contracts and Alice can deny them, although no private key leaked. SecureSign's registration requires the one-time "
     "challenge signature shown in Snippet 2; Eve can only sign it with her own key, so the registration is rejected "
     "(Figure 5.4). The same attempt through the real POST /api/keys endpoint is covered by an automated test.")
figure("fig17_lab_keysub.png", "5.4", "Lab scene 5: key substitution succeeds against a registry without proof-of-possession and is rejected by SecureSign.", 6.0)
heading("5.4 Non-Repudiation: Signed Receipts and a Hash-Chained Evidence Log", 2)
para("A valid signature proves who signed, but not when, and an ordinary log can be edited by anyone who controls the "
     "database, so a signer could still claim \"I never signed that\" or \"I signed a later version\". SecureSign therefore "
     "records every key registration and revocation, PDF signature, delivery and verification by the recipient as an "
     "evidence entry. Each entry is a receipt that the server signs and links to the previous entry (evidence.py):")
code('''def build_entry(key, seq, prev_hash, event, actor, details,
                time_iso=None):
    body = {"type": RECEIPT_TYPE, "version": 1, "seq": seq,
            "time": time_iso or utc_now_iso(), "event": event,
            "actor": actor, "details": details,
            "prev_hash": prev_hash}
    body_bytes = canonical(body)     # sorted keys: exact signed bytes
    signature = key.sign(body_bytes, ec.ECDSA(hashes.SHA256()))
    return {"seq": seq, "body": body_bytes.decode(),
            "entry_hash": sha256_hex(body_bytes),
            "signature": b64(signature)}

def verify_entries(entries, public_key):
    prev_hash, expected_seq = GENESIS_HASH, 1
    for e in entries:
        body = json.loads(e["body"])
        if e["seq"] != expected_seq or body["seq"] != e["seq"]:
            return broken(e, "missing or reordered entry")
        if body["prev_hash"] != prev_hash:
            return broken(e, "chain cut or entry inserted")
        if sha256_hex(e["body"].encode()) != e["entry_hash"]:
            return broken(e, "content edited")
        if not signature_ok(public_key, e["body"], e["signature"]):
            return broken(e, "forged entry: server signature invalid")
        prev_hash, expected_seq = e["entry_hash"], e["seq"] + 1
    return {"ok": True, "count": expected_seq - 1}''')
para("Explanation: the receipt body fixes the event, the server time, the actor and the details (the PDF's SHA-256, the "
     "signature's SHA-256 and the signer's key fingerprint and algorithm). canonical() makes the encoding deterministic, so "
     "the same bytes are hashed, signed and later verified. prev_hash is the entry_hash of the previous entry, so every "
     "entry commits to the whole history before it; deleting, inserting, reordering or editing any entry breaks the chain "
     "at that point. The server signs each body with its ECDSA P-256 receipt key, so recomputing all hashes after an edit "
     "is still detected without that key. Users download their receipts from the signing page, the inbox or the history; "
     "a receipt can be checked in the app, which also confirms that it is still part of the server's chain (Figure 5.6), "
     "or offline with demos/verify_receipt.py and the server's public key from GET /api/receipts/server-key, which does "
     "not trust the key embedded in the file (Figure 5.7). Administrators can run the integrity check over the whole "
     "chain (Figure 5.8). Lab scene 6 shows the attacks this stops (Figure 5.5): Alice presents a later-dated receipt "
     "signed with her own key and it is rejected; an insider edits entry #2 and the hash check fails; the insider "
     "recomputes every hash and the server-signature check still fails, while Bob's downloaded receipt no longer matches "
     "the log. Together, the PDF signature (who), the receipt (what and when) and the chain (the history was not "
     "rewritten) give the non-repudiation that our midterm report described.")
figure("fig18_lab_evidence.png", "5.5", "Lab scene 6: a fake later-dated receipt is rejected, and editing the log is detected even after all hashes are recomputed.", 6.0)
figure("fig19_receipt_verify.png", "5.6", "Bob checks the delivery receipt in SecureSign: server signature valid, entry still in the chain.", 6.0)
figure("fig20_verify_receipt_cli.png", "5.7", "Offline verification of Alice's signing receipt with the trusted server key and the original PDF.", 5.8)
figure("fig21_admin_evidence.png", "5.8", "Administrator integrity check of the whole evidence chain.", 6.0)
heading("5.5 Security Fixes Made During Integration", 2)
para("While reviewing the SecureSign code for this report we found three security bugs. Each was fixed and is covered by a "
     "regression test in tests/test_hardening.py (Table 5.1).")
table_caption("Table 5.1. Security fixes made during integration")
table(["Problem", "Impact", "Fix"], [
    ["The rate limiter keyed requests on the left-most X-Forwarded-For value, which the client controls when no proxy overwrites it", "An attacker sends a different fake IP with every login request and is never rate-limited, which allows unlimited online password guessing", "client_address() uses the TCP peer address and trusts X-Forwarded-For only when TRUST_PROXY_HEADERS is set (enabled behind Caddy or Vercel, which overwrite the header). Test: 12 spoofed attempts → 10 × 401, then 429"],
    ["Login ran Argon2 only when the email existed", "Response time revealed which emails have an account (user enumeration)", "An Argon2 check against a dummy hash runs for unknown emails too"],
    ["database.py called text() for the PostgreSQL advisory lock without importing it", "The server crashed at start-up on PostgreSQL, i.e. in every production deployment", "Added the missing import"],
], [3000, 2900, 2887])
code('''def client_address(request: Request) -> str:
    if TRUST_PROXY_HEADERS:  # only behind a proxy that rewrites XFF
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"''')
para("We also integrated the lab without weakening the application: the lab page keeps script-src 'self' (all inline "
     "event handlers of the midterm prototype were replaced by event delegation), and only inline styles are allowed so "
     "that value fingerprints can be coloured. The lab is disabled by default when APP_ENV=production. We also fixed "
     "functional bugs in the web interface: a selected file could not be removed (every file picker now shows the file "
     "with a remove button and supports drag and drop), the signing result was displayed before the server had accepted "
     "the signature, and the display font was never loaded, so headings fell back to a serif font.")
heading("5.6 How an Attacker Might Still Try to Bypass the Defenses", 2)
bullet("**Stealing the encrypted key file and guessing the password:** PBKDF2 with 310,000 iterations slows guessing but does not stop it for weak passwords. A memory-hard KDF (Argon2id via WebAssembly), a non-extractable key in the browser, or a hardware token (WebAuthn, smart card, HSM) would be stronger.")
bullet("**Malicious JavaScript:** because signing happens in the browser, a cross-site scripting bug or a compromised server could serve code that steals the decrypted key. The strict CSP, HttpOnly session cookie and no inline scripts reduce this risk, but users must still trust the server that delivers the code.")
bullet("**Social engineering of trust:** proof-of-possession proves that a key belongs to an account, not that the account belongs to the real person. Eve can register as \"Alice Nguyen\" with her own key. Users must compare fingerprints through another channel before marking a key as trusted; a PKI with identity-verified certificates would solve this.")
bullet("**Biased or partially leaked ECDSA nonces and fault attacks:** RFC 6979 removes reuse, but side channels (Minerva, TPM-Fail) or glitching a deterministic signer can still leak d. Production code must use a constant-time library; hedged nonces counter fault attacks.")
bullet("**Attacking the receipt service itself:** whoever obtains the server's receipt key, or controls the server clock, can issue false receipts or rewrite the whole chain with valid signatures. The key should live in an HSM or a secret store (SECURESIGN_RECEIPT_KEY_PEM), and the head hash of the chain should be published regularly or time-stamped by an external RFC 3161 authority, so an insider cannot silently rewrite history.")
bullet("**Signing a different view of the document:** SecureSign signs the exact PDF bytes, so any change is detected, but a PDF can contain active content or render differently in different viewers. PAdES with PDF/A and trusted timestamps addresses this in real systems.")

# ---------------- CHAPTER 6
heading("CHAPTER 6. CONCLUSION AND LIMITATIONS", 1, page_break=True)
heading("6.1 Conclusion", 2)
para("We met both success criteria set in our midterm plan. SecureSign signs PDFs correctly with RSA-PSS and rejected every "
     "tampered document and impostor key with both RSA-PSS and ECDSA P-256, and in the Security Lab the ECDSA private key was recovered from only two "
     "signed PDFs with a reused nonce, after which a forged invoice passed both the cryptography library and OpenSSL. The "
     "RFC 6979 patch, RSA-PSS, proof-of-possession and the signed evidence chain each defeated their attack. The "
     "demonstration supports the central thesis of our midterm report: the mathematics of RSA and ECC was never broken. "
     "Every failure came from implementation details: a reused number, missing padding, a registry that did not check who "
     "owns a key, or a log that could be rewritten.")
heading("6.2 Hardest Technical Challenges", 2)
bullet("**Reproducing the bug at all.** The cryptography library (correctly) never exposes the nonce, so we had to implement P-256 point arithmetic and ECDSA ourselves and then prove it interoperates with the library and with OpenSSL.")
bullet("**Keeping the private key on the client.** Signing in the browser with Web Crypto means the server can never see the key, but key storage, encryption parameters and the proof-of-possession protocol all had to be designed carefully so the server can still trust which account a key belongs to.")
bullet("**Integrating the lab into a secured application.** The midterm prototype used inline scripts and a single global state. Moving it into SecureSign required per-user state, session and CSRF protection, and rewriting the page so that it works under a strict Content Security Policy.")
bullet("**Making non-repudiation verifiable.** A receipt must be checkable by a third party without trusting the server, so the signed bytes had to be canonical, the verifier had to ignore the key embedded in the file, and the chain had to be appended under a lock so that two requests cannot create the same sequence number.")
bullet("**Keeping the demo honest.** The relying party always verifies with an independent, audited library (and OpenSSL), never with our own code, and every screenshot in this report was produced by a script that drives the real application.")
heading("6.3 Limitations", 2)
bullet("Signatures are detached RSA-PSS or ECDSA .sig files, not embedded PAdES signatures, and there are no CA-issued certificates or revocation (CRL/OCSP). A valid signature proves who holds the key, not a verified legal identity.")
bullet("Receipts are issued by SecureSign itself, not by an independent RFC 3161 time-stamping authority, so they are only as trustworthy as the server's clock and receipt key. By default that key is generated once and stored in the database; deployments should provide it through SECURESIGN_RECEIPT_KEY_PEM. Key rotation for receipts is not implemented.")
bullet("The lab's ecc_core.py uses Python big integers and a branching double-and-add loop. It is slow and not constant-time, so it must never sign real data; SecureSign itself does not use it.")
bullet("The nonce attack covers only exact reuse. Partially biased nonces would need a lattice (Hidden Number Problem) attack, which we did not implement.")
bullet("There is no multi-factor authentication, malware scanning of uploads, storage quota or email notification. PDFs are limited to 4 MiB on Vercel, and the in-memory rate limiter is only suitable for a single local instance (Upstash Redis is used on Vercel).")
bullet("Security Lab state is kept in server memory, so it is lost on restart and is not shared between server instances.")
heading("6.4 Improvements for a Real-World Production Environment", 2)
para("Issue X.509 certificates from a trusted CA (or an internal PKI) after identity verification, and embed signatures "
     "as PAdES with RFC 3161 timestamps so that documents stay verifiable after a key expires. Keep the receipt key in an "
     "HSM and anchor the head of the evidence chain externally (an RFC 3161 timestamp or a public transparency log in the "
     "style of Certificate Transparency). Keep users' private keys in "
     "non-extractable storage such as WebAuthn authenticators, smart cards or an HSM/KMS. Add multi-factor authentication, "
     "a shared rate limiter, upload scanning, backups and monitoring, and an independent penetration test before opening "
     "registration to the public. For ECDSA, use only constant-time libraries with deterministic or hedged nonces, or "
     "Ed25519 (RFC 8032). Plan for post-quantum migration to ML-DSA (FIPS 204), because Shor's algorithm breaks both RSA "
     "and ECC.")

# ---------------- REFERENCES
heading("REFERENCES", 1, page_break=True)
refs = [
    '[1] National Institute of Standards and Technology, "Digital Signature Standard (DSS)," FIPS PUB 186-5, Feb. 2023.',
    '[2] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, Aug. 2015.',
    '[3] T. Pornin, "Deterministic Usage of the Digital Signature Algorithm (DSA) and Elliptic Curve Digital Signature Algorithm (ECDSA)," RFC 6979, IETF, Aug. 2013. Section 3.2 (algorithm) and Appendix A.2.5 (P-256 test vector used in our unit tests).',
    '[4] K. Moriarty, B. Kaliski, J. Jonsson and A. Rusch, "PKCS #1: RSA Cryptography Specifications Version 2.2," RFC 8017, IETF, Nov. 2016.',
    '[5] K. Moriarty, B. Kaliski and A. Rusch, "PKCS #5: Password-Based Cryptography Specification Version 2.1," RFC 8018, IETF, Jan. 2017.',
    '[6] A. Biryukov, D. Dinu, D. Khovratovich and S. Josefsson, "Argon2 Memory-Hard Function for Password Hashing and Proof-of-Work Applications," RFC 9106, IETF, Sep. 2021.',
    '[7] J. Schaad, "Internet X.509 Public Key Infrastructure Certificate Request Message Format (CRMF)," RFC 4211, IETF, Sep. 2005. Section 4 (proof-of-possession).',
    '[8] W3C, "Web Cryptography API," W3C Recommendation, Jan. 2017. [Online]. Available: https://www.w3.org/TR/WebCryptoAPI/',
    '[9] Certicom Research, "SEC 2: Recommended Elliptic Curve Domain Parameters," v2.0, 2010. P-256 constants.',
    '[10] fail0verflow (bushing, marcan, sven), "Console Hacking 2010: PS3 Epic Fail," 27th Chaos Communication Congress (27C3), Dec. 2010.',
    '[11] D. Boneh and V. Shoup, A Graduate Course in Applied Cryptography, v0.6, Stanford University, 2023. [Online]. Available: https://toc.cryptobook.us/',
    '[12] Python Cryptographic Authority, "cryptography documentation: Elliptic curve signing / RSA." [Online]. Available: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/',
    '[13] OWASP Foundation, "Password Storage Cheat Sheet," "Cross-Site Request Forgery Prevention Cheat Sheet" and "Authentication Cheat Sheet." [Online]. Available: https://cheatsheetseries.owasp.org/',
    '[14] S. Ramírez, "FastAPI documentation." [Online]. Available: https://fastapi.tiangolo.com/',
    '[15] J. Jancar et al., "Minerva: The curse of ECDSA nonces," IACR TCHES 2020(4); D. Moghimi et al., "TPM-FAIL: TPM meets Timing and Lattice Attacks," USENIX Security 2020.',
    '[16] C. Adams, P. Cain, D. Pinkas and R. Zuccherato, "Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)," RFC 3161, IETF, Aug. 2001.',
    '[17] B. Laurie, A. Langley and E. Kasper, "Certificate Transparency," RFC 6962, IETF, Jun. 2013. Hash-based append-only logs.',
    '[18] S. Haber and W. S. Stornetta, "How to Time-Stamp a Digital Document," Journal of Cryptology, vol. 3, no. 2, pp. 99–111, 1991.',
    '[19] Trieu Ngoc Van Anh, Duong Tran Quoc Khanh and Nguyen Vo Thanh Tu, "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation," Midterm Report, Ton Duc Thang University, 2026.',
]
for r_ in refs:
    p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', after=120, line=360, lineRule='auto')
    sub(pPr, 'w:ind', left=567, hanging=567); sub(pPr, 'w:jc', val='both')
    run(p, r_); put(p)
p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', before=240, after=120, line=360, lineRule='auto'); sub(pPr, 'w:jc', val='both')
run(p, "AI assistance attribution: ", b=True)
run(p, "The group used Claude (Anthropic), an AI assistant, to help draft parts of the source code (the SecureSign web "
       "application, ECDSA support, the receipt and evidence-log service, the Security Lab integration, ecc_core.py, attack.py, "
       "the demo scripts and the tests), to review the code for security bugs (the three fixes in Section 5.5), to automate "
       "the screenshots and diagram, and to draft this report. The group reviewed, executed and tested all code (37/37 tests pass, the RFC 6979 output matches the official "
       "test vector, and the forged PDF was independently checked with OpenSSL) and is responsible for the final content. "
       "No code was copied from StackOverflow. The P-256 constants and the RFC 6979 algorithm follow references [3] and [9].")
put(p)

# ------------------------------------------------------------------ lists of figures / tables
def list_entry(anchor_el, label, text, key):
    p = E('w:p'); pPr = sub(p, 'w:pPr')
    tabs = sub(pPr, 'w:tabs'); sub(tabs, 'w:tab', val='right', leader='dot', pos=8770)
    sub(pPr, 'w:spacing', after=80); sub(pPr, 'w:ind', left=1300, hanging=1300)
    run(p, label, b=True); run(p, ' ' + text)
    r = sub(p, 'w:r'); sub(r, 'w:tab')
    run(p, page_label(key))
    anchor_el.addprevious(p)

for num, cap in FIGS:
    short = cap.rstrip('.')
    list_entry(LOF_ANCHOR, f"Figure {num}:", short, f"fig {num}")
LOF_ANCHOR.getparent().remove(LOF_ANCHOR)
TABLES = [("1.1", "Project metadata"), ("2.1", "Software and libraries"), ("2.2", "Source files and their roles"), ("2.3", "Demo accounts (development mode only)"),
          ("3.1", "Scenes of the Security Lab"), ("3.2", "Algorithms used and rationale"),
          ("4.1", "Mapping of the demonstration steps"), ("5.1", "Security fixes made during integration")]
for num, cap in TABLES:
    list_entry(LOT_ANCHOR, f"Table {num}:", cap, f"tab {num}")
LOT_ANCHOR.getparent().remove(LOT_ANCHOR)

# ------------------------------------------------------------------ table of contents
content = TOC.find(qn('w:sdtContent'))
ps = content.findall(qn('w:p'))
title_p, first_p, last_p = ps[0], ps[1], ps[-1]
toc2_tmpl = next((p for p in ps if p.find('.//' + qn('w:pStyle')) is not None
                  and p.find('.//' + qn('w:pStyle')).get(qn('w:val')) == 'TOC2'), None)
toc1_tmpl = ps[2]
for p in ps[1:-1]: content.remove(p)

def toc_par(tmpl, text, anchor, page, with_field_begin=False):
    p = copy.deepcopy(tmpl)
    # keep pPr and (for first entry) the field-begin runs, rebuild the hyperlink
    hl = p.find(qn('w:hyperlink'))
    hl.set(qn('w:anchor'), anchor)
    hl.find('.//' + qn('w:t')).text = text
    for instr in hl.iter(qn('w:instrText')):
        instr.text = f" PAGEREF {anchor} \\h "
    ts = hl.findall('.//' + qn('w:t'))
    ts[-1].text = page
    return p

for k, (lvl, text, anchor) in enumerate(TOC_ENTRIES):
    if k == 0:
        tmpl = first_p
    else:
        tmpl = toc1_tmpl if lvl == 1 else (toc2_tmpl if toc2_tmpl is not None else toc1_tmpl)
    last_p.addprevious(toc_par(tmpl, text, anchor, page_label(text)))

# Ask Word to refresh fields (TOC page numbers) on open
settings = d.settings.element
uf = settings.find(qn('w:updateFields'))
if uf is None:
    uf = E('w:updateFields', val='true'); settings.append(uf)

d.core_properties.title = "Final Report - Digital Signatures in Practice: SecureSign Cloud (N05_G05)"
d.save(OUT)
json.dump({"toc": [t for _, t, _ in TOC_ENTRIES], "figs": [f"Figure {n}." for n, _ in FIGS],
           "tabs": [f"Table {n}." for n, _ in TABLES]}, open(OUT + '.keys.json', 'w'), indent=1)
print("saved", OUT, len(TOC_ENTRIES), "toc entries,", len(FIGS), "figures")
