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
    ("API", "Application Programming Interface"),
    ("CLI", "Command-Line Interface"),
    ("CSPRNG", "Cryptographically Secure Pseudo-Random Number Generator"),
    ("DER", "Distinguished Encoding Rules"),
    ("ECC", "Elliptic Curve Cryptography"),
    ("ECDSA", "Elliptic Curve Digital Signature Algorithm"),
    ("GUI", "Graphical User Interface"),
    ("HMAC", "Hash-based Message Authentication Code"),
    ("HMAC-DRBG", "HMAC-based Deterministic Random Bit Generator"),
    ("HNP", "Hidden Number Problem"),
    ("HSM", "Hardware Security Module"),
    ("KMS", "Key Management Service"),
    ("MGF1", "Mask Generation Function 1"),
    ("PEM", "Privacy-Enhanced Mail (key file format)"),
    ("PKI", "Public Key Infrastructure"),
    ("PSS", "Probabilistic Signature Scheme"),
    ("RFC", "Request for Comments"),
    ("RSA", "Rivest–Shamir–Adleman (algorithm)"),
    ("SHA", "Secure Hash Algorithm"),
]:
    tr = copy.deepcopy(tmpl_row)
    tcs = tr.findall(qn('w:tc'))
    set_cell_text(tcs[0], a); set_cell_text(tcs[1], m)
    abbr.append(tr)
put(abbr)

heading("ABSTRACT", 1, page_break=True)
para("This report presents the practical phase of our project on digital signatures. Our midterm report analysed RSA and "
     "ECDSA, the role of hash functions and non-repudiation, and argued that real-world breaks come from implementation "
     "mistakes rather than from the mathematics. For the final phase we turned that analysis into a working, reproducible "
     "Python toolkit with a web-based demonstration GUI. Demo 1 shows correct use: RSA-2048 with PSS padding and ECDSA "
     "P-256 sign a contract, valid signatures are accepted, and a one-character modification or an impostor's key is "
     "rejected. Demo 2 is the attack. A signing service with a realistic bug generates its ECDSA nonce k only once and "
     "reuses it. From two public signatures alone, the attacker recovers k, then the private key d, forges a signature on "
     "a malicious invoice, and the forgery is accepted by the audited cryptography library. Demo 3 is the patch: the "
     "signer derives k with RFC 6979 (HMAC-DRBG). The same attack pipeline then finds no repeated r, recovers a wrong key, "
     "and the forgery is rejected. A bonus Demo 4 shows that textbook RSA is forgeable by multiplying signatures, while "
     "RSA-PSS blocks it. Every result is checked by an automated unit test suite, including the official RFC 6979 test "
     "vector, and both success criteria defined in the midterm plan were met.")
p = para("Keywords: digital signature, RSA-PSS, ECDSA, nonce reuse, private key recovery, RFC 6979, non-repudiation, demonstration.",
         indent=False, italic=True)

# ================================================================== MAIN BODY (arabic section)
CURRENT['before'] = None

# ---------------- CHAPTER 1
heading("CHAPTER 1. INTRODUCTION AND PROJECT METADATA", 1)
heading("1.1 Project Metadata", 2)
table_caption("Table 1.1. Project metadata")
table(["Item", "Details"], [
    ["Project topic", "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation (ECDSA Nonce-Reuse Attack and RFC 6979 Defense)"],
    ["Course", "Introduction to Information Security, Faculty of Information Technology, Ton Duc Thang University"],
    ["Instructor", "Ph.D. Huynh Ngoc Tu"],
    ["Group", "N05_G05"],
    ["Group members (names and IDs)", "Trieu Ngoc Van Anh (524H0005); Duong Tran Quoc Khanh (523H0040); Nguyen Vo Thanh Tu (523H0189)"],
    ["Repository link", "https://github.com/duongtranquockhanhwork/final-BMTT"],
], [2600, 6187])
heading("1.2 Executive Summary", 2)
para("For this project we built a small Python toolkit and an interactive web GUI that demonstrate both the correct use and "
     "the failure of digital signatures. The toolkit uses the audited cryptography library for every production-grade "
     "operation, plus a minimal, educational ECDSA (NIST P-256) implementation that lets us choose the nonce k, which is "
     "needed to reproduce the bug. The specific attack scenario we demonstrate is ECDSA nonce reuse: a signing service "
     "reuses the same k for two invoices, an attacker who only sees public data recovers the private key in milliseconds, "
     "and a forged invoice for 1,000,000 USD is accepted as genuine by a relying party that uses an audited verifier. We "
     "then patch the signer with RFC 6979 deterministic nonces and show, with the same unchanged attack code, that the "
     "attack no longer works. A bonus demo contrasts textbook RSA (forgeable) with RSA-PSS (secure).")
heading("1.3 Relation to the Midterm Plan", 2)
para("Section 5.2 of our midterm report defined two success criteria. (1) The correct-use demo succeeds if valid signatures "
     "verify and any tampered message is rejected for both RSA and ECDSA. (2) The attack demo succeeds if the ECDSA private "
     "key is recovered purely from two signatures sharing a reused nonce, and a signature forged with that key is accepted. "
     "Both criteria are met (Chapter 4). We also went beyond the plan by adding the RFC 6979 patch (Chapter 5), the textbook "
     "RSA demo and an automated test suite.")
para("Two tools changed from the plan. The ecdsa package was replaced by our own small P-256 module (ecc_core.py), because "
     "audited libraries deliberately never let the caller choose k, and we need that to reproduce the bug; correctness is "
     "proven by cross-checking against the cryptography library. Jupyter Notebook was replaced by a local web GUI "
     "(web_demo.py), which is easier to present live and needs no extra dependency.")
heading("1.4 Report Structure", 2)
para("Chapter 2 describes the lab environment needed to reproduce the demonstration. Chapter 3 explains the architecture, "
     "the key code snippets and the algorithms. Chapter 4 walks through the live demonstration step by step with "
     "screenshots. Chapter 5 presents the patch and discusses how an attacker might still try to bypass it. Chapter 6 "
     "concludes with the challenges, limitations and possible improvements.")

# ---------------- CHAPTER 2
heading("CHAPTER 2. LAB ENVIRONMENT AND TOOLS SETUP", 1, page_break=True)
heading("2.1 Hardware and Virtual Machines", 2)
para("Any x86-64 or Apple Silicon laptop or PC is sufficient. We developed and ran the demonstration on Windows 10 Pro 64-bit "
     "and re-tested it on macOS. No virtual machine, special hardware or second host is needed. All four demos finish in "
     "under 5 seconds and use less than 100 MB of RAM.")
heading("2.2 Software and Libraries", 2)
table_caption("Table 2.1. Software and libraries")
table(["Component", "Version", "Purpose"], [
    ["Python", "3.11.9 (3.10+ works)", "Runtime for all scripts and the GUI server"],
    ["cryptography", "≥ 44 (tested 46.0.7 and 50.0.1)", "Audited RSA/ECDSA, key generation and verification by the relying party; version 44+ is needed for deterministic_signing in Demo 3"],
    ["Python standard library", "hashlib, hmac, secrets, unittest, http.server", "SHA-256, HMAC-DRBG, CSPRNG, unit tests, local web server for the GUI"],
    ["Web browser", "Any modern browser (Chrome, Edge, Firefox, Safari)", "Displays the demonstration GUI"],
    ["OpenSSL CLI", "3.x (optional)", "openssl_demo.sh cross-check of sign/verify/tamper"],
], [2000, 2700, 4087])
heading("2.3 Network Configuration", 2)
para("None. The whole demonstration runs offline on a single machine. The GUI server binds only to 127.0.0.1 (port 8000 by "
     "default), so it is not reachable from other hosts. The \"public channel\" between the signing service, the attacker "
     "and the relying party is simulated in-process. The console demos also write the intercepted signatures and the forged "
     "signature as JSON files to source/output/, so the data the attacker uses is exactly what a network sniffer or a public "
     "ledger would expose.")
heading("2.4 Reproduction Steps and Project Structure", 2)
code("""python -m venv .venv
.venv\\Scripts\\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v   # 8 automated checks
python web_demo.py                 # web GUI at http://127.0.0.1:8000 (macOS: python3)
python run_all.py --pause          # console version of all demos
bash openssl_demo.sh               # optional OpenSSL CLI cross-check""")
table_caption("Table 2.2. Source files and their roles")
table(["File", "Role"], [
    ["ecc_core.py", "P-256 point arithmetic, ECDSA sign/verify with explicit nonce k, RFC 6979 nonce generator, conversion to/from cryptography key objects"],
    ["attack.py", "find_reused_nonce(), recover_nonce(), recover_private_key()"],
    ["demo1_correct_use.py", "RSA-PSS and ECDSA sign/verify, tamper test, impostor-key test"],
    ["demo2_nonce_reuse_attack.py", "Vulnerable signer, then key recovery, forgery and verification by the victim"],
    ["demo3_defense_rfc6979.py", "Patched signer, attack re-run, cross-check against the library"],
    ["demo4_rsa_textbook_vs_pss.py", "Bonus: textbook RSA multiplicative forgery vs. RSA-PSS"],
    ["web_demo.py", "Demonstration GUI server (standard library only), one JSON endpoint per demo step"],
    ["web/index.html, web/advanced.html", "Story-mode demo page (English/Vietnamese) and technical view (full values, unit tests)"],
    ["tests/test_signatures.py", "Unit tests (curve, interoperability, RFC 6979 vector, attack, defense)"],
], [3000, 5787])

# ---------------- CHAPTER 3
heading("CHAPTER 3. CORE IMPLEMENTATION AND CODE ANALYSIS", 1, page_break=True)
heading("3.1 Architecture and Flow Logic", 2)
para("The program models four actors: a signing service (the victim that owns the private key d), a public channel (signed "
     "documents are published, e.g. invoices, firmware images or blockchain transactions), an attacker who can only read "
     "public data, and a relying party that verifies signatures with the trusted public key Q using the audited "
     "cryptography library.")
para("Flow of the attack (Demo 2): (1) the VulnerableSigner generates a key pair and a single nonce k at start-up; (2) it "
     "signs two invoices, and both signatures carry the same r because r = (k·G).x; (3) the attacker groups intercepted "
     "signatures by r, finds the collision, and solves two linear equations for k and then d; (4) the recovered d is checked "
     "against the public key (d·G = Q); (5) d is imported into a normal cryptography private-key object to sign a malicious "
     "invoice; (6) the relying party verifies it with the real Q and accepts it. Demo 3 swaps only the nonce source for RFC "
     "6979 and re-runs the same pipeline unchanged, so any difference in the outcome is caused by the patch alone.")
figure("fig00_architecture.png", "3.1", "Program architecture. Top: nonce-reuse attack flow (Demo 2). Bottom: the same flow after the RFC 6979 patch (Demo 3).")
heading("3.2 Demonstration GUI", 2)
para("For the live presentation we built a web GUI (web_demo.py, web/index.html and web/advanced.html). It uses only the "
     "Python standard library (http.server), so no new dependency is needed. The server listens on 127.0.0.1, keeps the "
     "demo state in memory and exposes one JSON endpoint per action (for example /api/demo1/sign, /api/ecdsa/sign, "
     "/api/ecdsa/attack, /api/ecdsa/forge). Each endpoint calls exactly the same functions as the console demos "
     "(ecc_core.py, attack.py and the cryptography library), so every value on screen is computed live and nothing is "
     "pre-recorded. The relying party in the GUI always verifies with the cryptography library, never with our own code.")
para("The main page tells the demonstration as a story, so that a non-specialist audience can follow it. Four columns show "
     "the actors: the signer (Alice in Scene 1, the SecureSign invoice service in Scenes 2 and 3), the public Internet, the "
     "attacker Eve, and the verifier (Bob or the bank). The presenter presses one button (or the → key) per step; the step "
     "runs, new cards appear in the column of the actor who acted, and a plain-language explanation of what just happened "
     "is shown at the top. Long numbers are displayed as short coloured fingerprints, so equal values have equal colours: "
     "the audience can see at a glance that two signatures share the same r, or that the key computed by Eve is identical "
     "to the service's private key. Results are shown as green (protected) or red (attack succeeded) verdicts. The page "
     "can switch between English and Vietnamese, and a Show math switch reveals the equations and full values when "
     "technical questions are asked. A separate technical view (/advanced) shows full hexadecimal values, lets the "
     "presenter edit every message, and runs the unit test suite.")
table_caption("Table 3.1. Scenes of the demonstration GUI")
table(["Scene", "Steps (one click each)"], [
    ["1 · How it works", "Alice creates her key pair → signs the contract → Bob verifies (VALID) → Eve changes 1,000 to 9,000 USD (INVALID) → Eve signs with her own key (INVALID)"],
    ["2 · The attack", "SecureSign starts (bug: k reused) → signs invoice #1001 → signs invoice #1002 (same r) → Eve computes the private key (matches) → Eve's 1,000,000 USD invoice is accepted by the bank"],
    ["3 · The fix", "Same five steps with RFC 6979: different r → wrong key → forgery rejected; plus a byte-for-byte cross-check with the cryptography library"],
    ["4 · Bonus: RSA", "Alice signs 100 and 50 with textbook RSA → Eve multiplies the signatures, 5,000 is accepted → the same trick against RSA-PSS is rejected"],
], [2000, 6787])
heading("3.3 Key Code Snippets and Explanation", 2)
subhead("Snippet 1: The vulnerable signer (demo2_nonce_reuse_attack.py, ecc_core.py)")
code('''class VulnerableSigner:
    """The victim's signing service. BUG: the nonce is generated ONCE and reused."""
    def __init__(self):
        self.d, self.Q = E.generate_keypair()
        self._k = secrets.randbelow(E.N - 1) + 1   # random... but only ONCE  <-- BUG

    def sign(self, message: bytes):
        return E.ecdsa_sign(message, self.d, self._k)   # same k every call

def ecdsa_sign(message: bytes, d: int, k: int):
    h = hash_to_int(message)
    R = scalar_mult(k, G)
    r = R[0] % N
    if r == 0:
        raise ValueError("bad nonce: r == 0")
    s = inv(k, N) * (h + r * d) % N
    if s == 0:
        raise ValueError("bad nonce: s == 0")
    return r, s''')
para("Explanation: generate_keypair() draws d from a CSPRNG (secrets), so the key itself is strong. The bug is in __init__: "
     "the nonce k is also drawn from a CSPRNG, but only once, and stored in self._k. Every call to sign() therefore computes "
     "R = k·G with the same k, so the public value r = R.x mod n is identical across signatures. This leaks the fact that k "
     "was reused to anyone who looks. The signing equation s = k⁻¹(h + r·d) mod n is the standard ECDSA formula (FIPS 186-5). "
     "It is mathematically correct, which is why every signature still verifies and the bug goes unnoticed in normal "
     "testing. This is the same class of bug as the 2010 Sony PlayStation 3 firmware-signing key leak.")
subhead("Snippet 2: Private key recovery (attack.py)")
code('''def recover_nonce(m1: bytes, sig1, m2: bytes, sig2) -> int:
    r1, s1 = sig1
    r2, s2 = sig2
    if r1 != r2:
        raise ValueError("r values differ: the nonce was NOT reused, attack impossible")
    h1, h2 = hash_to_int(m1), hash_to_int(m2)
    if (s1 - s2) % N == 0:
        raise ValueError("s1 == s2: messages hash to the same value")
    return (h1 - h2) * inv(s1 - s2, N) % N

def recover_private_key(m1: bytes, sig1, k: int) -> int:
    r, s1 = sig1
    h1 = hash_to_int(m1)
    return (s1 * k - h1) * inv(r, N) % N''')
para("Explanation: the attacker uses only public data, namely two messages and their signatures. Since r1 = r2, both "
     "signatures share the unknown terms k and r·d. Subtracting s1 − s2 = k⁻¹(h1 − h2) cancels r·d, so "
     "k = (h1 − h2)·(s1 − s2)⁻¹ mod n. pow(x, -1, n) computes a modular inverse, which exists because n is prime. With k "
     "known, the first signing equation has a single unknown and gives d = (s1·k − h1)·r⁻¹ mod n. The guard r1 ≠ r2 → "
     "ValueError is what makes the attack fail against the patched signer in Demo 3.")
subhead("Snippet 3: Forgery accepted by an audited library (demo2_nonce_reuse_attack.py)")
code('''def victim_verify(public_key, message: bytes, sig) -> bool:
    try:
        public_key.verify(E.sig_to_der(sig), message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False

# --- in main(): forgery with the stolen key
stolen = E.to_crypto_private_key(d_rec)               # import into a normal library
forged_der = stolen.sign(evil, ec.ECDSA(hashes.SHA256()))
accepted = victim_verify(pub, evil, E.der_to_sig(forged_der))   # -> True''')
para("Explanation: the relying party does everything right. It uses the well-reviewed cryptography library and the "
     "authentic public key Q. Once d has leaked, the attacker becomes cryptographically indistinguishable from the real "
     "signer: ec.derive_private_key(d) rebuilds a normal private key, and its signature on the malicious invoice passes "
     "verify(). A signature only proves knowledge of d, so an implementation bug on the signer's side completely breaks "
     "integrity, authentication and non-repudiation for every message that key has ever signed or will sign.")
heading("3.4 Algorithms and Cryptography Used", 2)
table_caption("Table 3.2. Algorithms used and rationale")
table(["Algorithm", "Where used", "Why we chose it"], [
    ["ECDSA over NIST P-256 (secp256r1) with SHA-256", "Demos 1–3, ecc_core.py", "Most widely deployed ECC signature (TLS, FIDO2, code signing). About 128-bit security with 256-bit keys (RSA needs about 3072 bits) and a ~70-byte signature. Its dependence on a secret per-signature nonce is exactly the weakness we demonstrate."],
    ["RSASSA-PSS, RSA-2048, SHA-256, MGF1 (RFC 8017)", "Demos 1 and 4", "The modern, provably secure RSA signature encoding. Its random salt and hash-based padding remove the multiplicative structure of textbook RSA. Chosen over PKCS#1 v1.5 because PSS has a security proof."],
    ["SHA-256 (FIPS 180-4)", "All demos", "Collision-resistant 256-bit digest that matches the P-256 order, so no truncation is needed. MD5 and SHA-1 were rejected because practical collisions exist."],
    ["RFC 6979 deterministic nonce (HMAC-DRBG / HMAC-SHA256)", "Demo 3 (the patch)", "k = f(d, H(m)) is unique per message and unpredictable without d, and needs no runtime RNG. It also protects against broken or low-entropy RNGs, which caused the PS3 and 2013 Android Bitcoin wallet incidents."],
    ["Textbook RSA s = m^d mod n", "Demo 4 only (insecure baseline)", "Shown only as a counter-example to explain why padding is mandatory."],
], [2400, 1900, 4487])
para("Implementation choices: all production-grade operations (RSA, key generation, verification by the victim) use the "
     "cryptography library, which wraps OpenSSL. We wrote our own P-256 arithmetic only because no audited library lets "
     "the caller choose k. To make sure this educational code is correct, (a) our public keys match the library's for the "
     "same d, (b) our signatures verify under the library, and (c) our RFC 6979 output matches the official test vector "
     "(RFC 6979 A.2.5) and is byte-identical to cryptography's deterministic_signing=True.")

# ---------------- CHAPTER 4
heading("CHAPTER 4. STEP-BY-STEP DEMONSTRATION WALKTHROUGH", 1, page_break=True)
para("The live demonstration is run from the GUI (python web_demo.py, then open http://127.0.0.1:8000) by pressing the "
     "→ key once per step. Each step can also be reproduced in the console with python run_all.py --pause; screenshots of "
     "both are included below. Table 4.1 maps the three steps required by the course template to the GUI.")
table_caption("Table 4.1. Mapping of the demonstration steps to the GUI")
table(["Template step", "GUI", "Console"], [
    ["Step 1: Initialization", "Scene 1 (all steps); Scene 2 steps 1–3: service starts, two invoices signed with the same r", "unit tests, demo1_correct_use.py, openssl_demo.sh, start of demo2"],
    ["Step 2: Execution / The attack", "Scene 2 step 4: Eve computes the private key", "demo2 steps 3–4"],
    ["Step 3: Verification / The result", "Scene 2 step 5: forged invoice accepted by the bank", "demo2 steps 5–6"],
    ["Patch (Chapter 5)", "Scene 3 (same steps with RFC 6979) and Scene 4 (RSA-PSS)", "demo3, demo4"],
], [2300, 3900, 2587])
heading("4.1 Step 1: Initialization", 2)
para("Description: install the dependencies, then run the unit test suite to prove that the toolkit is correct before the "
     "demo (Figure 4.1; the same suite can be run from the technical view of the GUI). Next, run Demo 1 (GUI Scene 1) to establish the "
     "baseline. Correctly implemented RSA-PSS and ECDSA accept the genuine contract and reject both a one-character "
     "modification (1,000 → 9,000 USD, which flips 117 of 256 hash bits) and an impostor's key (Figures 4.2 and 4.3). "
     "The same check with the OpenSSL CLI gives matching results (Figure 4.4). Finally, start Demo 2: the vulnerable signing "
     "service generates its key pair (GUI Scene 2, step 1). The private key d is shown (blurred in the GUI) only so the audience can compare it "
     "later. The service publishes two ordinary invoices, and both signatures verify as VALID while sharing the same r "
     "value (Figure 4.5).")
figure("fig01_unit_tests.png", "4.1", "8/8 unit tests pass, including the official RFC 6979 test vector.", 5.6)
figure("fig02_demo1_correct_use.png", "4.2", "Demo 1 (console). Valid signatures accepted; tampered message and impostor key rejected.", 5.0)
figure("fig10_gui_demo1.png", "4.3", "GUI Scene 1. The genuine contract is accepted; the tampered contract (1,000 → 9,000 USD) and Eve's own signature are rejected.", 6.0)
figure("fig08_openssl.png", "4.4", "The same sign/verify/tamper flow with the OpenSSL command line.", 5.0)
figure("fig03_demo2_init.png", "4.5", "Demo 2 initialization. Two published signatures with identical r.", 5.6)
heading("4.2 Step 2: Execution / The Attack", 2)
para("Description: the attacker scans the intercepted signatures and finds two with the same r, which proves that k was "
     "reused. Applying k = (h1 − h2)/(s1 − s2) mod n and d = (s1·k − h1)/r mod n recovers the 256-bit private key in "
     "milliseconds. It is identical to the victim's hidden d, and d·G equals the published public key Q (Figure 4.6). In "
     "the GUI this is Scene 2, step 4: the key computed by Eve appears with the same colour fingerprint as the service's "
     "private key, which is then revealed for comparison; Show math displays both equations and the full values.")
figure("fig04_demo2_attack.png", "4.6", "Nonce and private key recovered from two public signatures.", 5.6)
heading("4.3 Step 3: Verification / The Result", 2)
para("Description: the attacker signs \"Invoice #6666: pay 1,000,000 USD to Attacker's account\" with the stolen key. The "
     "relying party verifies it with the victim's real public key using cryptography's ECDSA verify(), and the result is "
     "VALID (Figures 4.7 and 4.8; in the GUI the invoice pays 1,000,000 USD to Eve's account). The forged invoice is indistinguishable from a genuine one, so integrity, authentication "
     "and non-repudiation are all broken: the real owner can no longer prove which signatures they did not make. This meets "
     "the attack success criterion defined in Section 5.2 of our midterm report.")
figure("fig05_demo2_forgery.png", "4.7", "Forged signature accepted by the relying party (console).", 5.6)
figure("fig11_gui_attack.png", "4.8", "GUI Scene 2 after all five steps: identical r values on the Internet, private key recovered by Eve, and the forged 1,000,000 USD invoice accepted by the bank.", 6.0)

# ---------------- CHAPTER 5
heading("CHAPTER 5. VULNERABILITY PATCH AND DEFENSE MECHANISM", 1, page_break=True)
heading("5.1 The Patch: RFC 6979 Deterministic Nonces", 2)
para("The root cause is a nonce that is not unique per message. We replaced it with RFC 6979 deterministic nonce "
     "generation, the same approach used by libsecp256k1 (Bitcoin), Ed25519 by design, and the cryptography library's "
     "deterministic_signing option. Only the nonce source changes. The key, curve, hash and signing equation stay the same.")
code('''class PatchedSigner:
    """FIX: a fresh deterministic nonce per message (RFC 6979)."""
    def sign(self, message: bytes):
        k = E.rfc6979_nonce(self.d, message)       # k depends on (d, H(m))
        return E.ecdsa_sign(message, self.d, k)

def rfc6979_nonce(d: int, message: bytes) -> int:
    h1 = hashlib.sha256(message).digest()
    V = b"\\x01" * 32
    K = b"\\x00" * 32
    K = hmac.new(K, V + b"\\x00" + _int2octets(d) + _bits2octets(h1), hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    K = hmac.new(K, V + b"\\x01" + _int2octets(d) + _bits2octets(h1), hashlib.sha256).digest()
    V = hmac.new(K, V, hashlib.sha256).digest()
    while True:
        V = hmac.new(K, V, hashlib.sha256).digest()
        k = int.from_bytes(V, "big")
        if 1 <= k < N:
            return k
        K = hmac.new(K, V + b"\\x00", hashlib.sha256).digest()
        V = hmac.new(K, V, hashlib.sha256).digest()''')
para("Explanation: K and V are the state of an HMAC-DRBG seeded with the private key d and the message hash h1. Because "
     "HMAC-SHA256 is a pseudo-random function keyed by secret material, k is (1) the same only when both d and the message "
     "are the same, in which case the signature is also the same and nothing new leaks, (2) different and unrelated for any "
     "different message, and (3) unpredictable to anyone who does not know d. The rejection loop keeps 1 ≤ k < n. No "
     "runtime random number generator is involved, so a broken, seeded or low-entropy RNG can no longer leak the key.")
heading("5.2 Verification of the Patch", 2)
para("Re-running the unchanged Demo 2 attack pipeline against the patched signer gives: r1 ≠ r2, so recover_nonce() refuses "
     "to run. Forcing the formulas anyway yields a guess d′ with d′·G ≠ Q. The forgery made with d′ is REJECTED by the "
     "relying party. Our signature is also byte-identical to the one produced by cryptography with "
     "deterministic_signing=True, which confirms the patch matches the standard (Figures 5.1 and 5.2).")
figure("fig06_demo3_defense.png", "5.1", "Demo 3 (console). The same attack fails against the RFC 6979 signer.", 5.6)
figure("fig12_gui_defense.png", "5.2", "GUI Scene 3: different r values, wrong key, forgery rejected, and output byte-identical to the audited library.", 6.0)
heading("5.3 Related Defense: RSA Padding", 2)
para("Textbook RSA signatures are multiplicative: from sign(100) and sign(50) the attacker computes sign(5000) = s1·s2 mod n "
     "without the private key, and it verifies. With RSASSA-PSS the same product is rejected, because each signature covers "
     "a randomly salted, hashed encoding rather than the raw number (Figures 5.3 and 5.4).")
figure("fig07_demo4_rsa.png", "5.3", "Demo 4 (console). Textbook RSA forgery succeeds; RSA-PSS blocks it.", 5.6)
figure("fig13_gui_demo4.png", "5.4", "GUI Scene 4: the multiplied textbook RSA signature is accepted for 5,000; the same trick is rejected by RSA-PSS.", 6.0)
heading("5.4 How an Attacker Might Still Try to Bypass the Defense", 2)
para("RFC 6979 removes nonce reuse, but it does not make ECDSA invulnerable:")
bullet("**Biased or partially leaked nonces:** if even a few bits of each k leak (timing, cache or power side channels, as in the Minerva (2019) and TPM-Fail (2019) attacks), lattice attacks on the Hidden Number Problem recover d from a few hundred signatures. Our ecc_core.py is not constant-time and would be vulnerable, which is why production code must use a constant-time library.")
bullet("**Fault injection:** with deterministic nonces, signing the same message twice while glitching one run (voltage or clock glitch, Rowhammer) can leak d. Hedged signatures (RFC 6979 plus fresh randomness) or verifying each signature before releasing it counter this.")
bullet("**Key theft instead of math:** malware, a leaked .pem file (our demo saves unencrypted PEM keys for transparency) or an insider. Countermeasures: HSM, TPM or secure-enclave storage, encrypted key files, and least privilege.")
bullet("**Malleability and verification bugs:** (r, n − s) is also a valid signature, which matters for systems that use signatures as IDs (Bitcoin enforces low-s). Weak verifiers that skip range checks or accept r = 0 (e.g. Java's \"Psychic Signatures\" bug, CVE-2022-21449) can be bypassed. Our ecdsa_verify() performs the 1 ≤ r, s < n checks.")
bullet("**Substituting the public key:** if the relying party obtains Q over an unauthenticated channel, the attacker can replace it with their own key. A PKI with certificate chain validation and revocation (CRL/OCSP) is required.")

# ---------------- CHAPTER 6
heading("CHAPTER 6. CONCLUSION AND LIMITATIONS", 1, page_break=True)
heading("6.1 Conclusion", 2)
para("We met both success criteria set in our midterm plan. Correctly used RSA-PSS and ECDSA rejected every tampered message, "
     "and the ECDSA private key was recovered from only two signatures with a reused nonce, after which a forged signature "
     "passed an audited verifier. The RFC 6979 patch defeated the same attack. The demonstration supports the central "
     "thesis of our midterm report: the mathematics of RSA and ECC was never broken. Every failure came from "
     "implementation details.")
heading("6.2 Hardest Technical Challenges", 2)
bullet("**Reproducing the bug at all.** The cryptography library (correctly) never exposes the nonce, so we had to implement P-256 point arithmetic and ECDSA ourselves and then prove it interoperates with the library.")
bullet("**Getting RFC 6979 exactly right.** The bits2octets reduction mod n and the HMAC-DRBG state updates are easy to get subtly wrong, so we validated against the official test vector and the library's deterministic mode.")
bullet("**Keeping the demo honest.** The victim must verify with an independent, trusted library, not with our own code, so the audience can see the forgery is a real break and not a bug in our verifier. The GUI follows the same rule: it calls the real functions instead of showing pre-recorded results.")
heading("6.3 Limitations", 2)
bullet("ecc_core.py uses Python big integers with affine coordinates and a branching double-and-add loop. It is slow (about 10 ms per scalar multiplication) and not constant-time, so it leaks timing and must never sign real data.")
bullet("The attack covers only exact nonce reuse with the same key. Partially biased nonces would need a lattice (HNP) attack, which we did not implement.")
bullet("Only NIST P-256 and SHA-256 are supported, with no Ed25519, secp256k1 or SHA-3.")
bullet("The network is simulated in-process, keys are stored as unencrypted PEM files for transparency, and the GUI server is single-user, keeps state in memory and has no authentication (it only listens on 127.0.0.1).")
bullet("Demo 3 requires cryptography 44 or newer for the cross-check step (it is skipped on older versions).")
heading("6.4 Improvements for a Real-World Production Environment", 2)
para("Use only an audited, constant-time library (OpenSSL, BoringSSL, libsecp256k1 or libsodium) with deterministic or hedged "
     "nonces, or switch to Ed25519 (RFC 8032), which is deterministic by design. Keep private keys in an HSM or cloud KMS "
     "with access logging. Distribute public keys through a PKI with revocation. Enforce low-s and strict DER parsing. Add a "
     "monitor that alerts when two signatures from the same key share an r value. Plan for post-quantum migration to ML-DSA "
     "(FIPS 204), because Shor's algorithm breaks both RSA and ECC.")

# ---------------- REFERENCES
heading("REFERENCES", 1, page_break=True)
refs = [
    '[1] National Institute of Standards and Technology, "Digital Signature Standard (DSS)," FIPS PUB 186-5, Feb. 2023.',
    '[2] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, Aug. 2015.',
    '[3] T. Pornin, "Deterministic Usage of the Digital Signature Algorithm (DSA) and Elliptic Curve Digital Signature Algorithm (ECDSA)," RFC 6979, IETF, Aug. 2013. Section 3.2 (algorithm) and Appendix A.2.5 (P-256 test vector used in our unit tests).',
    '[4] K. Moriarty, B. Kaliski, J. Jonsson and A. Rusch, "PKCS #1: RSA Cryptography Specifications Version 2.2," RFC 8017, IETF, Nov. 2016.',
    '[5] Certicom Research, "SEC 2: Recommended Elliptic Curve Domain Parameters," v2.0, 2010. P-256 constants.',
    '[6] fail0verflow (bushing, marcan, sven), "Console Hacking 2010: PS3 Epic Fail," 27th Chaos Communication Congress (27C3), Dec. 2010.',
    '[7] D. Hankerson, A. Menezes and S. Vanstone, Guide to Elliptic Curve Cryptography, Springer, 2004. Point addition and double-and-add algorithms.',
    '[8] D. Boneh and V. Shoup, A Graduate Course in Applied Cryptography, v0.6, Stanford University, 2023. [Online]. Available: https://toc.cryptobook.us/',
    '[9] Python Cryptographic Authority, "cryptography documentation: Elliptic curve signing / RSA." [Online]. Available: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/',
    '[10] OpenSSL Project, "openssl-dgst manual page." [Online]. Available: https://docs.openssl.org/3.5/man1/openssl-dgst/',
    '[11] J. Jancar et al., "Minerva: The curse of ECDSA nonces," IACR TCHES 2020(4); D. Moghimi et al., "TPM-FAIL: TPM meets Timing and Lattice Attacks," USENIX Security 2020.',
    '[12] N. Madden, "Psychic Signatures in Java (CVE-2022-21449)," ForgeRock blog, Apr. 2022.',
    '[13] Python Software Foundation, "http.server — HTTP servers," Python 3 documentation. Used for the demonstration GUI.',
    '[14] Trieu Ngoc Van Anh, Duong Tran Quoc Khanh and Nguyen Vo Thanh Tu, "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation," Midterm Report, Ton Duc Thang University, 2026.',
]
for r_ in refs:
    p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', after=120, line=360, lineRule='auto')
    sub(pPr, 'w:ind', left=567, hanging=567); sub(pPr, 'w:jc', val='both')
    run(p, r_); put(p)
p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', before=240, after=120, line=360, lineRule='auto'); sub(pPr, 'w:jc', val='both')
run(p, "AI assistance attribution: ", b=True)
run(p, "The group used Claude (Anthropic), an AI assistant, to help draft parts of the demonstration source code (ecc_core.py, "
       "attack.py, demo scripts, the web GUI and unit tests), the screenshot and diagram generation, and the first draft of "
       "this report. The group reviewed, executed and tested all code (8/8 unit tests pass, and the RFC 6979 output was "
       "verified against the official test vector) and is responsible for the final content. No code was copied from "
       "StackOverflow. The P-256 constants and the RFC 6979 algorithm follow references [3] and [5].")
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
TABLES = [("1.1", "Project metadata"), ("2.1", "Software and libraries"), ("2.2", "Source files and their roles"),
          ("3.1", "Scenes of the demonstration GUI"), ("3.2", "Algorithms used and rationale"), ("4.1", "Mapping of the demonstration steps to the GUI")]
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

d.core_properties.title = "Final Report - Digital Signatures in Practice (N05_G05)"
d.save(OUT)
json.dump({"toc": [t for _, t, _ in TOC_ENTRIES], "figs": [f"Figure {n}." for n, _ in FIGS],
           "tabs": [f"Table {n}." for n, _ in TABLES]}, open(OUT + '.keys.json', 'w'), indent=1)
print("saved", OUT, len(TOC_ENTRIES), "toc entries,", len(FIGS), "figures")
