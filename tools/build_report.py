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
     "that signs and verifies PDF documents with RSA-PSS or ECDSA P-256 and SHA-256. Each user generates a key pair in the "
     "browser; the private key is encrypted with PBKDF2 and AES-256-GCM and never leaves the device, and a public key is "
     "accepted only after a challenge-response proof-of-possession. The server re-verifies every signature, isolates "
     "documents between sender and recipient, and protects accounts with Argon2id, CSRF tokens, rate limiting and a strict "
     "Content Security Policy. To guarantee non-repudiation, every key event, signature, delivery and verification becomes "
     "a server-signed, timestamped receipt in a SHA-256 hash-chained evidence log that can be verified offline. We analyse "
     "five attacks with flow diagrams (document tampering, key substitution, repudiation and log tampering, ECDSA nonce "
     "reuse, and password guessing behind a spoofed X-Forwarded-For header) and demonstrate in the running system that "
     "SecureSign detects or blocks them. While integrating the platform we found and fixed three security bugs. All "
     "results are covered by 21 automated tests.")
p = para("Keywords: digital signature, RSA-PSS, ECDSA, proof-of-possession, timestamped receipt, hash chain, non-repudiation, PDF signing.",
         indent=False, italic=True)

# ================================================================== MAIN BODY (arabic section)
CURRENT['before'] = None

# ---------------- CHAPTER 1
heading("CHAPTER 1. INTRODUCTION AND PROJECT METADATA", 1)
heading("1.1 Project Metadata", 2)
table_caption("Table 1.1. Project metadata")
table(["Item", "Details"], [
    ["Project topic", "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation (SecureSign Cloud: multi-user PDF signing with RSA-PSS / ECDSA and signed, hash-chained receipts)"],
    ["Course", "Introduction to Information Security, Faculty of Information Technology, Ton Duc Thang University"],
    ["Instructor", "Ph.D. Huynh Ngoc Tu"],
    ["Group", "N05_G05"],
    ["Group members (names and IDs)", "Trieu Ngoc Van Anh (524H0005); Duong Tran Quoc Khanh (523H0040); Nguyen Vo Thanh Tu (523H0189)"],
    ["Repository link", "https://github.com/duongtranquockhanhwork/final-BMTT"],
], [2600, 6187])
heading("1.2 Executive Summary", 2)
para("We built SecureSign Cloud, a multi-user web application for signing PDF documents. It is the correct use of "
     "digital signatures: RSA-PSS or ECDSA P-256 keys are created and stored encrypted in the user's browser, the server "
     "re-verifies every signature and only accepts a public key after a proof-of-possession challenge, and every signing "
     "or delivery yields a server-signed, timestamped receipt in a hash-chained evidence log, so a signer cannot later "
     "deny it. The scenario we demonstrate is a defense: Alice signs a contract PDF and sends it to Bob, and we show how "
     "SecureSign stops an attacker who edits the PDF, an impostor who registers Alice's public key as her own, and a "
     "signer or insider who tries to deny the signature or rewrite the log. Each attack is explained with a flow diagram "
     "and its result is shown in the running system; ECDSA nonce reuse and a rate-limit bypass we fixed complete the "
     "analysis.")
heading("1.3 Relation to the Midterm Plan", 2)
para("Section 5.2 of our midterm report defined two success criteria. (1) The correct-use demo succeeds if valid signatures "
     "verify and any tampered message is rejected for both RSA and ECDSA. This is met in the production system: SecureSign "
     "signs real PDFs with RSA-PSS or ECDSA P-256 and rejects every modified document (Chapter 4). (2) The attack criterion "
     "was ECDSA private-key recovery from two signatures that share a nonce. For the final submission we kept the code "
     "focused on the delivered platform, so this attack is analysed with a step-by-step flow diagram and its equations "
     "(Section 4.2) together with the reason SecureSign is not affected, instead of a separate attack program.")
para("We went beyond the plan in the direction of the topic's third part, non-repudiation: a public-key registry with "
     "proof-of-possession, server-signed receipts and a tamper-evident evidence log, plus a review that found and fixed three "
     "security bugs. Jupyter Notebook was replaced by the SecureSign web application, which is easier to present live and "
     "is closer to a real deployment.")
heading("1.4 Report Structure", 2)
para("Chapter 2 describes the lab environment needed to reproduce the demonstration. Chapter 3 explains the architecture, "
     "the key code snippets and the algorithms. Chapter 4 walks through the demonstration: the normal workflow, the attack "
     "flows and their results. Chapter 5 explains the defense mechanisms, the security fixes we made while integrating the "
     "platform, and how an attacker might still try to bypass the defenses. Chapter 6 concludes with the challenges, "
     "limitations and possible improvements.")

# ---------------- CHAPTER 2
heading("CHAPTER 2. LAB ENVIRONMENT AND TOOLS SETUP", 1, page_break=True)
heading("2.1 Hardware and Virtual Machines", 2)
para("Any x86-64 or Apple Silicon laptop or PC is sufficient. We developed and ran the demonstration on macOS and Windows "
     "10 Pro 64-bit. No virtual machine, special hardware or second host is needed: two browser windows (or one normal and "
     "one private window) are enough to play Alice and Bob. The server uses less than 150 MB of RAM; RSA key generation "
     "takes about 0.2 seconds in the browser and ECDSA key generation a few milliseconds.")
heading("2.2 Software and Libraries", 2)
table_caption("Table 2.1. Software and libraries")
table(["Component", "Version", "Purpose"], [
    ["Python", "3.11.9 (3.11+ required)", "Runtime for the server, the receipt verifier and the tests"],
    ["FastAPI, Uvicorn", "≥ 0.115 / ≥ 0.30 (tested 0.165 / 0.54)", "Web API and ASGI server"],
    ["SQLAlchemy + SQLite / PostgreSQL", "≥ 2.0 (tested 2.1)", "Users, sessions, public keys, documents, audit log and evidence chain (SQLite locally, PostgreSQL in deployment)"],
    ["cryptography", "≥ 44 (tested 50.0)", "Server-side RSA-PSS and ECDSA verification, key parsing and policy, receipt signing and verification"],
    ["argon2-cffi", "≥ 23.1 (tested 25.1)", "Argon2id password hashing"],
    ["Web Crypto API", "Any modern browser (Chrome, Edge, Firefox, Safari)", "RSA-PSS and ECDSA P-256 key generation and signing, PBKDF2 and AES-256-GCM private-key encryption in the browser"],
    ["pytest, httpx", "≥ 8.3 / ≥ 0.27 (tested 9.2 / 0.28)", "Automated test suite"],
    ["OpenSSL / LibreSSL CLI", "3.x / 3.3 (optional)", "Independent verification of ECDSA .sig files"],
    ["Docker, Caddy (optional)", "Compose v2, Caddy 2", "Deployment with PostgreSQL and automatic HTTPS (not needed for the demo)"],
], [2300, 2400, 4087])
heading("2.3 Network Configuration", 2)
para("For the demonstration the server binds only to 127.0.0.1 on port 8000, so it is not reachable from other hosts. Web "
     "Crypto requires a secure context, which browsers grant to localhost; any other address must use HTTPS. Locally the "
     "app uses SQLite in source/storage/, does not require email verification and creates the demo accounts of Table 2.3. "
     "For an Internet deployment, "
     "docker-compose.yml runs the app behind Caddy, which obtains a TLS certificate, overwrites the X-Forwarded-For header "
     "and forwards to the app; PostgreSQL is only reachable on the internal Docker network. Receipts can be checked "
     "offline, without any network access to the server, once its receipt public key has been obtained.")
heading("2.4 Reproduction Steps and Project Structure", 2)
code("""python -m venv .venv
.venv\\Scripts\\activate     # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -v                # 21 automated checks
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# web app:      http://127.0.0.1:8000   (demo accounts: Table 2.3)
python demos/verify_receipt.py R.json --server-key S.pem --pdf F.pdf""")
table_caption("Table 2.2. Source files and their roles")
table(["File", "Role"], [
    ["backend/app/main.py", "FastAPI application: registration and login, key registry, signing record, verification, document exchange, administration, security middleware"],
    ["backend/app/crypto_service.py", "verify_signature() for RSA-PSS and ECDSA P-256, verify_proof_of_possession(), public-key policy and fingerprints"],
    ["backend/app/evidence.py", "Server-signed receipts, SHA-256 hash-chained evidence log, chain and receipt verification"],
    ["backend/app/security.py", "Argon2id password hashing, hashed session tokens, double-submit CSRF check, admin role check"],
    ["backend/app/database.py", "SQLAlchemy models (including the evidence entries) and admin bootstrap"],
    ["frontend/index.html, app.js", "SecureSign web app; key generation, encryption and signing in the browser"],
    ["demos/verify_receipt.py", "Offline receipt verifier for a judge or auditor (does not trust the server)"],
    ["backend/app/demo_seed.py, demo_data/", "Demo accounts created at start-up in development, their encrypted key files and sample PDFs"],
    ["tests/", "pytest suite (RSA and ECDSA, multi-user isolation, receipts and evidence chain, security fixes, demo accounts)"],
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
para("SecureSign has three tiers (Figure 3.1). The browser performs every operation that needs the private key. The "
     "FastAPI backend stores only public keys, enforces access control and re-checks every signature with the "
     "cryptography library before it records or forwards anything, and writes every security-relevant event to a "
     "server-signed, hash-chained evidence log. The database and file storage hold accounts, sessions, public keys, "
     "documents, the audit log and the evidence chain.")
figure("fig00_architecture.png", "3.1", "Architecture of SecureSign Cloud and the threat each defense addresses.")
para("Flow of the signing workflow (Figure 3.2): (1) Alice registers; her password is hashed with Argon2id and she receives "
     "an HttpOnly session cookie and a CSRF token. (2) Her browser generates an RSA-2048 or ECDSA P-256 key pair, encrypts "
     "the private key with a password and offers it as a .key.json file. (3) To register the public key, the server issues "
     "a one-time random challenge; the browser signs it, and the server links the key to Alice only if the proof verifies. "
     "(4) To sign, the browser decrypts the key locally, signs the PDF bytes with RSA-PSS or ECDSA (the algorithm is fixed "
     "by the registered key, never by the client) and produces a detached .sig file; the server re-verifies it and returns "
     "a signed receipt. (5) When Alice sends the PDF and .sig to Bob, the server verifies them against Alice's registered "
     "key, stores them in Bob's inbox and issues a delivery receipt; only the sender and the recipient can download or "
     "verify the document, and its receipts are visible only to them and to administrators. (6) Bob verifies the document, which is also recorded, and can mark Alice's key "
     "as trusted after comparing its fingerprint through another channel. (7) Any receipt can later be checked online or "
     "offline, and the administrator can check the integrity of the whole chain.")
figure("flow_signing.png", "3.2", "Signing workflow: key registration with proof-of-possession, signing, delivery and receipts.", 6.0)
heading("3.2 Demonstration GUI", 2)
para("The SecureSign web app (Vietnamese interface) has a dashboard, key management, signing, verification with a receipt "
     "checker, document sending, an inbox, a personal audit history with a receipt for each recorded event and, for "
     "administrators, user management and the evidence-log integrity check (Figures 3.3 and 3.4). Administrators can "
     "suspend accounts and change roles, but cannot read users' private documents, and the last active administrator "
     "cannot be removed. Every file picker shows the chosen file with its size and a remove (✕ Gỡ) button and accepts drag "
     "and drop. Table 3.1 summarises the threats we analyse and where each defense is shown.")
figure("fig08_admin.png", "3.3", "Administrator view: accounts, roles, status, keys and documents per user.", 6.0)
figure("fig09_history.png", "3.4", "Personal audit trail with a downloadable server-signed receipt for each recorded event.", 6.0)
table_caption("Table 3.1. Threats, defenses and where they are demonstrated")
table(["Threat (attacker goal)", "SecureSign defense", "Shown in"], [
    ["Tampering: change a signed PDF", "Signature over the exact PDF bytes, re-verified by the server and by the recipient", "Figures 4.7, 4.11"],
    ["Key substitution: register another user's public key", "One-time challenge, proof-of-possession, unique key fingerprints", "Figure 4.8"],
    ["Repudiation: deny or back-date a signature, edit the log", "Server-signed receipts, SHA-256 hash chain, offline verifier, admin integrity check", "Figures 4.9, 4.12–4.14"],
    ["Private-key recovery from ECDSA nonce reuse", "Audited ECDSA in Web Crypto with a fresh nonce per signature", "Figure 4.10"],
    ["Online password guessing with a spoofed X-Forwarded-For", "Rate limit keyed on the TCP peer address (fixed bug)", "Figure 5.1"],
], [2900, 3700, 2187])
heading("3.3 Key Code Snippets and Explanation", 2)
subhead("Snippet 1: Key generation, private-key protection and signing in the browser (frontend/app.js)")
code('''const ALGORITHMS = {          // label and importParams omitted here
  "RSA-PSS": {
    generate: {name: "RSA-PSS", modulusLength: 2048,
               publicExponent: new Uint8Array([1, 0, 1]),
               hash: "SHA-256"},
    signParams: {name: "RSA-PSS", saltLength: PSS_SALT_LENGTH}},
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
const aesKey = await crypto.subtle.deriveKey({name: "PBKDF2", salt,
    iterations: PBKDF2_ITERATIONS, hash: "SHA-256"},  // 310,000
    material, {name: "AES-GCM", length: 256}, false, ["encrypt"]);
const encrypted = await crypto.subtle.encrypt(
    {name: "AES-GCM", iv}, aesKey, pkcs8);   // only this is saved

async function signAndCheck(alg, privateKey, publicKey, data) {
  const p = ALGORITHMS[alg].signParams;
  const raw = new Uint8Array(
      await crypto.subtle.sign(p, privateKey, data));
  if (!(await crypto.subtle.verify(p, publicKey, raw, data)))
    throw new Error("Private Key and Public Key do not match.");
  // ECDSA: Web Crypto returns r||s; server and OpenSSL expect DER
  return alg === "ECDSA-P256" ? ecdsaRawToDer(raw) : raw;
}''')
para("Explanation (error messages are shown in English here; the application displays them in Vietnamese):", indent=False, after=80)
bullet("**ALGORITHMS:** only two schemes exist, RSA-PSS 2048 with e = 65537 and a 32-byte salt, and ECDSA on P-256, both with SHA-256. Fixing the parameters in one table means a user cannot pick a weak key size, curve or hash.")
bullet("**generateKey(...):** the browser's Web Crypto API creates the key pair with the operating system's CSPRNG. The private key exists only inside the browser.")
bullet("**exportKey(\"pkcs8\")**, **salt**, **iv:** the private key is exported only to be encrypted at once; the 16-byte salt and 12-byte IV are fresh random values, so two key files never share them.")
bullet("**importKey(\"raw\", password) / deriveKey(PBKDF2):** PBKDF2-HMAC-SHA256 with 310,000 iterations turns the user's password into a 256-bit AES key, which makes every offline password guess expensive.")
bullet("**encrypt(AES-GCM):** AES-256-GCM encrypts the key and adds an authentication tag, so a wrong password or a modified key file fails to decrypt instead of producing a wrong key. Only this ciphertext is saved in the .key.json file; nothing secret is sent to the server.")
bullet("**signAndCheck(...):** signs the PDF bytes (RSA-PSS with a random salt, or ECDSA with a fresh random nonce from the browser), then immediately verifies the new signature with the public key from the same key file, so a damaged or mismatched key file is detected before anything is sent.")
bullet("**ecdsaRawToDer(raw):** Web Crypto returns ECDSA signatures as raw r||s; converting them to DER makes them readable by the server and by OpenSSL. An ECDSA signature is about 72 bytes, compared with 256 bytes for RSA-2048.")
subhead("Snippet 2: Server-side checks: proof-of-possession and re-verification (crypto_service.py, main.py)")
code('''def verify_proof_of_possession(public_key, challenge: str,
                               proof_b64: str) -> bool:
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
if not verify_proof_of_possession(public_key,
        challenge.challenge_value, payload.proof_signature):
    raise HTTPException(400, "Could not prove ownership of the key.")
challenge.used_at = utc_now()

# POST /api/documents/send
result = verify_signature(pdf_bytes, signature_bytes,
                          key.public_key_pem.encode())
if not result["valid"]:
    raise HTTPException(400, "Signature does not match PDF and key.")''')
para("Explanation (error messages translated from Vietnamese):", indent=False, after=80)
bullet("**verify_proof_of_possession():** decodes the proof strictly (validate=True rejects malformed Base64) and verifies it as a signature on the challenge with the submitted public key. The scheme follows the key type, so the client cannot choose a weaker algorithm. Any decoding or verification error returns False instead of raising, so no error path can accept a key.")
bullet("**select(KeyChallenge)...:** the challenge must belong to the logged-in user, must not have been used and must not have expired (5 minutes). A proof made for someone else's challenge, or an old proof, is useless.")
bullet("**if not challenge / if not verify_proof_of_possession(...):** a public key is public, so anyone can copy it from the directory; only the holder of the matching private key can sign the fresh challenge. This is what blocks the key-substitution attack (Attack 2).")
bullet("**challenge.used_at = utc_now():** marks the challenge as consumed, so the same proof cannot be replayed. Key fingerprints are also unique, so a key can belong to only one account.")
bullet("**verify_signature(...) in /api/documents/send:** the server never trusts the browser's claim that a signature is valid. Before a signing event is recorded or a document is delivered, it re-checks the PDF and .sig against the sender's registered key with the audited cryptography library, which stops a tampered PDF (Attack 1) from ever reaching the recipient.")
subhead("Snippet 3: Signed receipts in a hash-chained evidence log (evidence.py)")
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

    def broken(e, reason):        # entries before e are intact
        return {"ok": False, "count": expected_seq - 1,
                "broken_at": e["seq"], "reason": reason}

    for e in entries:
        body = parse_body(e)
        if e["seq"] != expected_seq or body.get("seq") != e["seq"]:
            return broken(e, "Missing or reordered entry.")
        if body.get("prev_hash") != prev_hash:
            return broken(e, "prev_hash mismatch: chain cut.")
        if sha256_hex(e["body"].encode()) != e["entry_hash"]:
            return broken(e, "Content edited: SHA-256 mismatch.")
        if not signature_ok(public_key, e["body"], e["signature"]):
            return broken(e, "Server signature invalid.")
        prev_hash, expected_seq = e["entry_hash"], e["seq"] + 1
    return {"ok": True, "count": expected_seq - 1, "broken_at": None,
            "head_hash": prev_hash, "reason": OK_REASON}''')
para("Explanation (error messages translated from Vietnamese):", indent=False, after=80)
bullet("**body = {...}:** each receipt fixes the event, the server time, the actor and the details (the PDF's SHA-256, the signature's SHA-256 and the signer's key fingerprint and algorithm), plus **prev_hash**, the entry_hash of the previous entry. Through prev_hash every entry commits to the whole history before it.")
bullet("**canonical(body):** JSON with sorted keys and no spaces, so exactly the same bytes are hashed, signed and later verified by anyone.")
bullet("**key.sign(...ECDSA(SHA256)):** the server signs the receipt with its ECDSA P-256 receipt key. Only the server can produce a valid receipt, so a user cannot forge or back-date one, and the server cannot later deny having issued it.")
bullet("**verify_entries():** walks the chain in order. A wrong sequence number means an entry was deleted or reordered; a prev_hash mismatch means the chain was cut or an entry inserted; a SHA-256 mismatch means an entry was edited; an invalid server signature means the entry was rewritten, even if the attacker recomputed every hash (Attack 3). broken() reports the first bad entry and how many entries before it are intact.")
bullet("Entries are appended under a lock (and a PostgreSQL advisory lock in deployment), so two requests can never create the same sequence number.")
heading("3.4 Algorithms and Cryptography Used", 2)
table_caption("Table 3.2. Algorithms used and rationale")
table(["Algorithm", "Where used", "Why we chose it"], [
    ["RSASSA-PSS, RSA-2048, e = 65537, SHA-256, MGF1-SHA256, 32-byte salt (RFC 8017)", "SecureSign signing and verification (user choice), proof-of-possession", "Provably secure RSA signature encoding, supported natively by Web Crypto and by the cryptography library. The random salt and hash-based padding remove the multiplicative structure of textbook RSA. The server rejects keys below 2048 or above 4096 bits and any exponent other than 65537."],
    ["SHA-256 (FIPS 180-4)", "PDF digests, key fingerprints, token hashes", "Collision-resistant 256-bit digest; MD5 and SHA-1 were rejected because practical collisions exist. A one-character change in the PDF changes about half of the 256 bits."],
    ["PBKDF2-HMAC-SHA256 (310,000 iterations) + AES-256-GCM", "Encrypted private-key file in the browser", "The only password-based KDF and authenticated cipher available in every browser's Web Crypto API. GCM detects any modification of the key file."],
    ["Argon2id (t = 3, 64 MiB, p = 2)", "Account passwords on the server", "Memory-hard hash recommended by OWASP; makes GPU password cracking expensive if the database leaks."],
    ["ECDSA over NIST P-256 with SHA-256 (DER)", "SecureSign signing and verification (user choice)", "The most widely deployed ECC signature: about 128-bit security with a 256-bit key and a ~72-byte signature (RSA needs about 3072 bits for the same level). Its dependence on a secret per-signature nonce is exactly the weakness we analyse in Attack 4; the browser's implementation draws a fresh random nonce for every signature."],
    ["ECDSA P-256 server receipts + SHA-256 hash chain", "Evidence log and receipts", "The server signs each receipt (time, PDF digest, signer key) so it cannot be forged or back-dated; linking each entry to the SHA-256 of the previous one makes deletions, insertions and edits detectable. Small signatures keep the log compact."],
    ["RFC 6979 deterministic nonce (HMAC-DRBG / HMAC-SHA256)", "Recommended ECDSA nonce generation (analysis in Section 4.2)", "k = f(d, H(m)) is unique per message and unpredictable without d, and needs no runtime RNG, which also protects against broken or low-entropy RNGs."],
], [2400, 2000, 4387])
para("Implementation choices: SecureSign never implements cryptography itself. The browser uses Web Crypto and the server "
     "uses the cryptography library, which wraps OpenSSL. ECDSA signatures from the browser are converted to DER, so "
     "the same .sig file is also accepted by OpenSSL, which we used as an independent check.")

# ---------------- CHAPTER 4
heading("CHAPTER 4. STEP-BY-STEP DEMONSTRATION WALKTHROUGH", 1, page_break=True)
para("The demonstration runs on one laptop: start the server and open SecureSign in two browser windows for Alice and "
     "Bob (or sign in with the demo accounts of Table 2.3). Step 1 shows the normal workflow; Step 2 explains each attack "
     "with a flow diagram; Step 3 shows, in the running system, what happens when the attack is tried. Table 4.1 maps the "
     "three steps required by the course template to the demonstration.")
table_caption("Table 4.1. Mapping of the demonstration steps")
table(["Template step", "Demonstration", "Evidence"], [
    ["Step 1: Initialization", "Tests; register Alice and Bob; key pair + proof-of-possession; sign a contract PDF; send it; Bob verifies", "Figures 4.1–4.6"],
    ["Step 2: Execution / The attack", "Attack flows: tampering, key substitution, repudiation and log tampering, ECDSA nonce reuse", "Figures 4.7–4.10"],
    ["Step 3: Verification / The result", "Tampered PDF rejected; key substitution rejected; receipt verified in the app and offline; evidence-chain integrity check", "Figures 4.11–4.14"],
    ["Defense (Chapter 5)", "How each defense works, the security fixes, and how an attacker might still try to bypass them", "Figure 5.1, Table 5.1"],
], [2300, 4300, 2187])
heading("4.1 Step 1: Initialization", 2)
para("Description: install the dependencies and run the test suite to prove that the system is correct before the demo "
     "(Figure 4.1: 21 of 21 tests pass, covering RSA and ECDSA verification, multi-user isolation, receipts and the "
     "evidence chain, the receipt-key configuration, the demo accounts and the security fixes). Start the server; for the live demo we register Alice and "
     "Bob from scratch to show the full key set-up (the demo accounts skip this) (Figure 4.2). Alice creates an RSA-2048 "
     "key pair in the browser, downloads the encrypted private key and registers the public key; the success message "
     "confirms that the proof-of-possession was verified (Figure 4.3). She signs the contract PDF: the browser decrypts the "
     "key locally, signs, and the server re-verifies the signature before recording it and returns a server-signed, "
     "timestamped receipt (Figure 4.4). She sends the PDF and the .sig to Bob (Figure 4.5). Bob compares the fingerprint of "
     "Alice's key, marks it as trusted and verifies the document in his inbox: the signature is valid and the key is "
     "trusted (Figure 4.6).")
figure("fig01_tests.png", "4.1", "21/21 automated tests pass (RSA and ECDSA, multi-user isolation, receipts and evidence chain, security fixes, demo accounts).", 6.0)
figure("fig02_dashboard.png", "4.2", "SecureSign dashboard after registration.", 6.0)
figure("fig03_keys.png", "4.3", "Key pair generated in the browser; the public key is registered after a successful proof-of-possession.", 6.0)
figure("fig04_sign.png", "4.4", "PDF signed with RSA-PSS in the browser; digest, key fingerprint, algorithm, signature size and the server receipt number.", 6.0)
figure("fig05_send.png", "4.5", "Alice sends the signed PDF to Bob; the server verifies the signature before delivery.", 6.0)
figure("fig06_inbox_verified.png", "4.6", "Bob's inbox: the received PDF is verified as valid and signed with a key he trusts.", 6.0)
heading("4.2 Step 2: Execution / The Attack", 2)
para("Description: each attack is described as a flow between the actors. The diagrams show the attacker's steps in red "
     "and SecureSign's checks in green.")
subhead("Attack 1: Tampering with a signed PDF (integrity)")
para("Eve intercepts the contract and changes 1,000 USD to 9,000 USD, then forwards the edited PDF with Alice's original "
     ".sig file (Figure 4.7). She cannot produce a new signature, because that requires Alice's private key, which never "
     "leaves Alice's browser. In the demonstration we play Eve by uploading demo_data/contract-demo-tampered.pdf together "
     "with the original signature on the verification page.")
figure("flow_tamper.png", "4.7", "Attack 1 flow: tampering with a signed PDF.", 6.0)
subhead("Attack 2: Key substitution (authentication)")
para("A signature only proves that the holder of a given public key signed; the key registry decides who that holder is. "
     "Eve downloads Alice's public key from the directory (public keys are public) and tries to register it under her own "
     "account (Figure 4.8). If the registry accepted it, every PDF Alice signs would verify as \"signed by Eve\", so Eve "
     "could claim Alice's contracts and Alice could deny them, without any private key being stolen.")
figure("flow_keysub.png", "4.8", "Attack 2 flow: key substitution, and the proof-of-possession check that rejects it.", 6.0)
subhead("Attack 3: Repudiation and log tampering (non-repudiation)")
para("After signing, Alice claims that she never signed the contract, or that she signed it a week later, and presents a "
     "\"receipt\" with a later date that she signed with her own key. Separately, an insider with database access edits "
     "the evidence entry of the signature, and then recomputes every hash so that the chain looks consistent (Figure 4.9). "
     "We try both against the running system: Bob's downloaded receipt is checked in the app and offline, and the "
     "administrator runs the integrity check over the whole chain.")
figure("flow_repudiation.png", "4.9", "Attack 3 flow: repudiation with a fake receipt, and editing the evidence log.", 6.0)
subhead("Attack 4: ECDSA nonce reuse (analysis)")
para("ECDSA needs a new secret nonce k for every signature. A signer that reuses k produces two signatures with the same r, "
     "and anyone who sees two signed messages can compute k = (h1 − h2)/(s1 − s2) mod n and then the private key "
     "d = (s1·k − h1)/r mod n, after which every forgery verifies (Figure 4.10). This is the attack defined in our midterm "
     "plan and the cause of the 2010 Sony PlayStation 3 key leak. SecureSign does not implement ECDSA itself: the browser's "
     "Web Crypto implementation draws a fresh secret nonce for every signature, so two SecureSign signatures never share r "
     "and the two equations contain three unknowns.")
figure("flow_nonce.png", "4.10", "Attack 4 flow: private-key recovery from a reused ECDSA nonce, and why SecureSign's signatures are not affected.", 6.0)
heading("4.3 Step 3: Verification / The Result", 2)
para("Description: Attack 1 fails. Bob verifies the tampered copy with Alice's original signature and SecureSign reports "
     "the signature as invalid, because the SHA-256 of the edited PDF differs from the hash Alice signed (Figure 4.11). The "
     "same check runs on the server before any signature is recorded or any document is delivered.")
figure("fig07_verify_tampered.png", "4.11", "Attack 1 result: the tampered copy (1,000 → 9,000 USD) with the original signature is rejected.", 6.0)
para("Attack 2 fails. The server sends Eve a fresh one-time challenge; she can only sign it with her own private key, so "
     "verify_proof_of_possession() rejects the registration, and Alice's key fingerprint is already owned by Alice "
     "(Figure 4.8). The same attempt through the real POST /api/keys endpoint is covered by an automated test, and Eve's "
     "key list stays empty.")
para("Attack 3 fails. Bob's receipt for the delivery is valid: it is signed by the SecureSign receipt key and is still part "
     "of the server's chain, and it fixes who sent which PDF (SHA-256) at what time (Figure 4.12). Alice's own receipt is "
     "rejected because it is not signed by the SecureSign key. A judge who does not trust the server can check Alice's "
     "signing receipt offline with demos/verify_receipt.py, the server's public key and the original PDF (Figure 4.13). "
     "The administrator's integrity check walks the whole chain (Figure 4.14); editing an entry makes it report the exact "
     "entry where the hash no longer matches, and recomputing the hashes is reported as an invalid server signature, as "
     "shown in the flow of Figure 4.9 and tested automatically against the real database.")
figure("fig19_receipt_verify.png", "4.12", "Attack 3 result: Bob's delivery receipt is valid and still in the server's chain.", 6.0)
figure("fig20_verify_receipt_cli.png", "4.13", "Offline verification of Alice's signing receipt with the trusted server key and the original PDF.", 5.8)
figure("fig21_admin_evidence.png", "4.14", "Administrator integrity check of the whole evidence chain.", 6.0)
para("Attack 4 does not apply to SecureSign, for the reason shown in the lower half of Figure 4.10: every ECDSA signature "
     "carries a different r, so the key cannot be solved from public data.")

# ---------------- CHAPTER 5
heading("CHAPTER 5. VULNERABILITY PATCH AND DEFENSE MECHANISM", 1, page_break=True)
heading("5.1 Integrity and Authentication", 2)
para("Integrity comes from signing the exact PDF bytes through SHA-256: any change to the file changes the digest, and the "
     "signature no longer verifies. SecureSign never trusts the client's claim that a signature is valid; "
     "verify_signature() re-checks it with the cryptography library and the sender's registered key before a signing "
     "event is recorded, before a document is delivered and whenever the recipient verifies it (Snippet 2). The algorithm "
     "is taken from the registered key, so a client cannot downgrade a key to another scheme, and the key policy rejects "
     "RSA keys outside 2048–4096 bits, exponents other than 65537 and elliptic curves other than P-256.")
para("Authentication comes from binding each public key to exactly one account. Registration requires a signature on a "
     "random 32-byte challenge that belongs to the current user, expires after 5 minutes and can be used once, so only the "
     "holder of the private key can register it and an old proof cannot be replayed (Snippet 2, Attack 2). Key "
     "fingerprints are unique across accounts, revoked keys cannot be used for new documents, and each user marks other "
     "users' keys as trusted only after comparing fingerprints through another channel.")
heading("5.2 Non-Repudiation: Signed Receipts and a Hash-Chained Evidence Log", 2)
para("A valid signature proves who signed, but not when, and an ordinary log can be edited by anyone who controls the "
     "database. SecureSign therefore records every key registration and revocation, PDF signature, delivery and "
     "verification by the recipient as an evidence entry (Snippet 3). Users download their receipts from the signing page, "
     "the inbox or the history. A receipt can be checked in the app, which also confirms that it is still part of the "
     "server's chain, or offline with demos/verify_receipt.py and the server's public key from GET /api/receipts/server-key; "
     "the offline verifier deliberately ignores the key embedded in the receipt file, otherwise anyone could sign a fake "
     "receipt with their own key and embed that key. Together, the PDF signature (who), the receipt (what and when) and the "
     "chain (the history was not rewritten) give the non-repudiation that our midterm report described.")
heading("5.3 ECDSA Nonces", 2)
para("The nonce-reuse attack of Figure 4.10 is a property of the signer's implementation, not of ECDSA. SecureSign relies "
     "on audited implementations only: Web Crypto in the browser, which draws a fresh nonce from the operating system's "
     "CSPRNG for every signature, and the cryptography library on the server for verification and receipts. Where a library "
     "allows it, the recommended alternative is RFC 6979, which derives k = HMAC-DRBG(d, H(m)): the nonce is unique for "
     "every message and unpredictable without the private key, and no runtime random generator is needed, so a broken or "
     "low-entropy RNG can no longer leak the key. Ed25519 (RFC 8032) is deterministic by design.")
heading("5.4 Security Fixes Made During Integration", 2)
para("While reviewing the SecureSign code for this report we found three security bugs. Each was fixed and is covered by a "
     "regression test in tests/test_hardening.py (Table 5.1). Figure 5.1 shows the most serious one.")
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
figure("flow_ratelimit.png", "5.1", "Password guessing behind a spoofed X-Forwarded-For header, before and after the fix.", 6.0)
para("We also fixed "
     "functional bugs in the web interface: a selected file could not be removed (every file picker now shows the file "
     "with a remove button and supports drag and drop), the signing result was displayed before the server had accepted "
     "the signature, and the display font was never loaded, so headings fell back to a serif font.")
heading("5.5 How an Attacker Might Still Try to Bypass the Defenses", 2)
bullet("**Stealing the encrypted key file and guessing the password:** PBKDF2 with 310,000 iterations slows guessing but does not stop it for weak passwords. A memory-hard KDF (Argon2id via WebAssembly), a non-extractable key in the browser, or a hardware token (WebAuthn, smart card, HSM) would be stronger.")
bullet("**Malicious JavaScript:** because signing happens in the browser, a cross-site scripting bug or a compromised server could serve code that steals the decrypted key. The strict CSP, HttpOnly session cookie and no inline scripts reduce this risk, but users must still trust the server that delivers the code.")
bullet("**Social engineering of trust:** proof-of-possession proves that a key belongs to an account, not that the account belongs to the real person. Eve can register as \"Alice Nguyen\" with her own key. Users must compare fingerprints through another channel before marking a key as trusted; a PKI with identity-verified certificates would solve this.")
bullet("**Biased or partially leaked ECDSA nonces and fault attacks:** RFC 6979 removes reuse, but side channels (Minerva, TPM-Fail) or glitching a deterministic signer can still leak d. Production code must use a constant-time library; hedged nonces counter fault attacks.")
bullet("**Attacking the receipt service itself:** whoever obtains the server's receipt key, or controls the server clock, can issue false receipts or rewrite the whole chain with valid signatures. The key should live in an HSM or a secret store (SECURESIGN_RECEIPT_KEY_PEM), and the head hash of the chain should be published regularly or time-stamped by an external RFC 3161 authority, so an insider cannot silently rewrite history.")
bullet("**Signing a different view of the document:** SecureSign signs the exact PDF bytes, so any change is detected, but a PDF can contain active content or render differently in different viewers. PAdES with PDF/A and trusted timestamps addresses this in real systems.")

# ---------------- CHAPTER 6
heading("CHAPTER 6. CONCLUSION AND LIMITATIONS", 1, page_break=True)
heading("6.1 Conclusion", 2)
para("SecureSign signs PDFs correctly with RSA-PSS and ECDSA P-256 and rejected every tampered document and impostor key, "
     "which meets the correct-use criterion of our midterm plan. Each analysed attack was stopped by a specific mechanism: "
     "re-verification of the signature against the PDF bytes stopped tampering, proof-of-possession stopped key "
     "substitution, server-signed receipts in a hash chain stopped repudiation and log tampering, and audited ECDSA with a "
     "fresh nonce per signature avoids the private-key recovery of the nonce-reuse attack. The work supports the central "
     "thesis of our midterm report: the mathematics of RSA and ECC is not what breaks in practice; implementation details "
     "are, such as a reused number, a registry that does not check who owns a key, or a log that can be rewritten.")
heading("6.2 Hardest Technical Challenges", 2)
bullet("**Keeping the private key on the client.** Signing in the browser with Web Crypto means the server can never see the key, but key storage, encryption parameters and the proof-of-possession protocol all had to be designed carefully so the server can still trust which account a key belongs to.")
bullet("**Making non-repudiation verifiable.** A receipt must be checkable by a third party without trusting the server, so the signed bytes had to be canonical, the verifier had to ignore the key embedded in the file, and the chain had to be appended under a lock so that two requests cannot create the same sequence number.")
bullet("**Keeping the demo honest.** Every check uses an independent, audited library (and OpenSSL for ECDSA .sig files), never our own cryptographic code, and every screenshot in this report was produced by a script that drives the real application.")
bullet("**Interoperability between the browser and the server.** Web Crypto returns ECDSA signatures as raw r||s while the server and OpenSSL expect DER, and PKCS#8 keys exported by the browser had to be readable by Python for the demo data; both directions had to be tested end to end.")
heading("6.3 Limitations", 2)
bullet("Signatures are detached RSA-PSS or ECDSA .sig files, not embedded PAdES signatures, and there are no CA-issued certificates or revocation (CRL/OCSP). A valid signature proves who holds the key, not a verified legal identity.")
bullet("Receipts are issued by SecureSign itself, not by an independent RFC 3161 time-stamping authority, so they are only as trustworthy as the server's clock and receipt key. By default that key is generated once and stored in the database; deployments should provide it through SECURESIGN_RECEIPT_KEY_PEM. Key rotation for receipts is not implemented.")
bullet("The ECDSA nonce-reuse attack is analysed with a flow diagram and its equations, not executed, because audited libraries do not let the caller choose the nonce.")
bullet("There is no multi-factor authentication, malware scanning of uploads, storage quota or email notification. PDFs are limited to 4 MiB on Vercel, and the in-memory rate limiter is only suitable for a single local instance (Upstash Redis is used on Vercel).")
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
TABLES = [("1.1", "Project metadata"), ("2.1", "Software and libraries"), ("2.2", "Source files and their roles"),
          ("2.3", "Demo accounts (development mode only)"), ("3.1", "Threats, defenses and where they are demonstrated"),
          ("3.2", "Algorithms used and rationale"), ("4.1", "Mapping of the demonstration steps"),
          ("5.1", "Security fixes made during integration")]
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
