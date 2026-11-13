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
    ("DIGITAL SIGNATURES IN PRACTICE:", "SECURECHAT: A LIVE CLASSROOM"),
    ("RSA AND ECC, THE ROLE OF HASH FUNCTIONS,", "DEMONSTRATION OF DIGITAL SIGNATURES —"),
    ("AND THE GUARANTEE OF NON-REPUDIATION", "MESSAGE TAMPERING AND PRIVATE-KEY THEFT"),
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
        for tag in ('w:sz', 'w:szCs'):          # 8.5 pt so ~75 characters fit on one line
            el = r.find('.//' + qn(tag))
            if el is not None: el.set(qn('w:val'), '17')
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
    ("HSM", "Hardware Security Module"),
    ("HTTP", "HyperText Transfer Protocol"),
    ("JSON", "JavaScript Object Notation"),
    ("KMS", "Key Management Service"),
    ("LAN", "Local Area Network"),
    ("MITM", "Man-in-the-Middle (attack)"),
    ("PKI", "Public Key Infrastructure"),
    ("RSA", "Rivest–Shamir–Adleman (algorithm)"),
    ("SHA", "Secure Hash Algorithm"),
    ("TLS", "Transport Layer Security"),
    ("UID", "User Identifier"),
    ("URL", "Uniform Resource Locator"),

]:
    tr = copy.deepcopy(tmpl_row)
    tcs = tr.findall(qn('w:tc'))
    set_cell_text(tcs[0], a); set_cell_text(tcs[1], m)
    abbr.append(tr)
put(abbr)

heading("ABSTRACT", 1, page_break=True)
para("This report presents SecureChat, an interactive classroom demonstration that turns our midterm theory on digital "
     "signatures into a live, multi-user web application. Students in the room scan a QR code, create an account with just "
     "a name, and send messages to one another. Behind the scenes each account is given an ECDSA (NIST P-256 / SHA-256) key "
     "pair, every message is signed with the sender's private key, and the recipient verifies it with the sender's public "
     "key. The teacher runs an admin dashboard that shows every account and message live and acts as a man-in-the-middle to "
     "demonstrate two lessons. First, if the attacker changes the content of a message without the key, the recipient's "
     "signature check fails and the tampering is detected, which is integrity. Second, if the attacker steals the sender's "
     "private key, they can change the content and re-sign it, so the forgery still verifies and the recipient is fooled, "
     "which shows why protecting the private key is the whole game. The application uses the audited cryptography library "
     "for all signing and verification and keeps every account, key and message in memory only, wiping them when the demo "
     "ends. This directly extends the midterm conclusion that digital-signature schemes are broken in practice not by the "
     "mathematics but by implementation and key-handling mistakes.")
p = para("Keywords: digital signature, ECDSA, message integrity, tampering, private key theft, man-in-the-middle, "
         "non-repudiation, classroom demonstration.",
         indent=False, italic=True)

# ================================================================== MAIN BODY (arabic section)
CURRENT['before'] = None

# ---------------- CHAPTER 1
heading("CHAPTER 1. INTRODUCTION AND PROJECT METADATA", 1)
heading("1.1 Project Metadata", 2)
table_caption("Table 1.1. Project metadata")
table(["Item", "Details"], [
    ["Project topic", "SecureChat: a classroom demonstration of digital signatures. A multi-user chat where every message is ECDSA-signed; the teacher plays the attacker to show message tampering and the effect of private-key theft."],
    ["Course", "Introduction to Information Security, Faculty of Information Technology, Ton Duc Thang University"],
    ["Instructor", "Ph.D. Huynh Ngoc Tu"],
    ["Group", "N05_G05"],
    ["Group members (names and IDs)", "Trieu Ngoc Van Anh (524H0005); Duong Tran Quoc Khanh (523H0040); Nguyen Vo Thanh Tu (523H0189)"],
    ["Repository link", "https://github.com/duongtranquockhanhwork/final-BMTT (folder secure-chat-demo)"],
], [2600, 6187])
heading("1.2 Executive Summary", 2)
para("We built SecureChat, a small web application that lets a whole class take part in a digital-signature demonstration "
     "at the same time. A student opens the join page by scanning a QR code, types a name, and immediately gets an ECDSA "
     "key pair and a chat screen. When a student sends a message, SecureChat signs the exact text with the sender's private "
     "key; when the message arrives, the recipient can press a button to verify the signature against the sender's public "
     "key. The specific scenario we demonstrate is a man-in-the-middle on the message channel, played live by the teacher "
     "from an admin dashboard. In the first part the attacker only edits the content of a message in transit: the recipient "
     "checks the signature and sees it is invalid, so the change is caught. In the second part the attacker first steals the "
     "sender's private key (revealed from the dashboard) and re-signs the edited message, so the recipient now sees a valid "
     "signature and is fooled. The contrast between the two outcomes is the core teaching point.")
heading("1.3 Relation to the Midterm Theory Report", 2)
para("Our midterm report explained how RSA and ECDSA signatures provide integrity, authentication and non-repudiation, and "
     "argued that real-world failures come from implementation and key-handling mistakes rather than from the algorithms. "
     "SecureChat makes those abstract ideas tangible for an audience. Integrity is shown directly: a one-character change to "
     "a signed message makes the signature fail. Non-repudiation and authentication are shown from the opposite side: they "
     "hold only as long as the private key stays secret, so once the key is stolen the attacker becomes indistinguishable "
     "from the real sender. The application therefore turns the midterm's central sentence, choosing a strong algorithm is "
     "necessary but not sufficient, into something the class can see on their own phones.")
heading("1.4 Report Structure", 2)
para("Chapter 2 describes the environment needed to run the demonstration. Chapter 3 explains the architecture, the key "
     "code and the algorithms. Chapter 4 walks through the live demonstration step by step with screenshots. Chapter 5 "
     "discusses what the signature already defends against, the real vulnerability (key theft) and how it is mitigated. "
     "Chapter 6 concludes with the challenges, limitations and possible improvements.")

# ---------------- CHAPTER 2
heading("CHAPTER 2. LAB ENVIRONMENT AND TOOLS SETUP", 1, page_break=True)
heading("2.1 Hardware and Devices", 2)
para("One laptop or PC runs the server (the teacher's machine). Each participant uses any device with a web browser, "
     "typically a phone, to scan the QR code and chat. No special hardware is needed. The server is light: it keeps all "
     "state in memory and comfortably handles a classroom of several dozen participants.")
heading("2.2 Software and Libraries", 2)
table_caption("Table 2.1. Software and libraries")
table(["Component", "Version", "Purpose"], [
    ["Python", "3.11 (3.10+ works)", "Runs the server (on macOS/Linux the command is python3)"],
    ["cryptography", ">= 44 (tested 46.0.7)", "Audited ECDSA P-256 key generation, signing and verification"],
    ["segno", ">= 1.6", "Renders the join URL as a QR code (optional; without it the URL is shown as text)"],
    ["Python standard library", "http.server, json, socket, secrets, threading, unittest", "Local web server, JSON API, LAN address, random passcode and tokens, thread-safe state, automated tests"],
    ["Web browser", "Any modern browser (Chrome, Safari, Edge, Firefox)", "Student chat and teacher dashboard; no app install needed"],
    ["Docker (optional)", "Engine 20+ with Compose", "Run the server in a container with one command, without installing Python locally"],
], [2000, 2500, 4287])
heading("2.3 Network Configuration", 2)
para("The server listens on all interfaces (0.0.0.0) on port 8070 by default and prints a join URL built from the laptop's "
     "LAN address, for example http://192.168.1.50:8070/. For students to join from their phones, the laptop and the phones "
     "must be on the same Wi-Fi network, and the laptop firewall must allow incoming connections on that port. Inside Docker "
     "the container cannot see the laptop's Wi-Fi address, so it is passed in with SC_PUBLIC_HOST. The admin dashboard is "
     "protected by a six-digit passcode printed only in the server console, so students cannot open it. Nothing is sent "
     "outside the local network: there is no database and no external service.")
heading("2.4 Running the Demo and Project Structure", 2)
code("""# Option A - Python
pip install -r requirements.txt
python3 run.py --passcode 123456
#   -> prints the join URL, the dashboard URL and the ADMIN PASSCODE

# Option B - Docker (set SC_PUBLIC_HOST to the laptop's Wi-Fi IP first)
docker compose up --build -d

# Automated tests (16 checks)
python3 -m unittest discover -s tests -v""")
para("Without --passcode (or SC_ADMIN_PASSCODE under Docker) a new random passcode is generated every time the server "
     "starts, so fixing it is recommended for a class. Students open the join URL or scan the QR code on the dashboard and "
     "pick a name; the teacher opens <url>/admin and enters the passcode.")
table_caption("Table 2.2. Source files and their roles")
table(["File", "Role"], [
    ["run.py", "Entry point: finds the LAN address, starts the server, prints the join URL and admin passcode"],
    ["server/crypto.py", "ECDSA P-256 / SHA-256 key generation, signing and verification (cryptography library)"],
    ["server/state.py", "In-memory, thread-safe store of accounts and messages, the intercept queue and the tamper / forge logic"],
    ["server/app.py", "HTTP routing and the JSON API for students and the admin"],
    ["server/qr.py", "QR code for the join URL (segno)"],
    ["web/join.html", "Student: create an account with a name (one account per device)"],
    ["web/chat.html", "Student: conversations sorted by latest message, unread badges, verify-signature button; separate list and conversation screens on phones"],
    ["web/admin.html, assets/admin.js", "Teacher: live dashboard, intercept queue and the fake-message console"],
    ["tests/test_state.py", "16 automated regression tests: joining, delivery, intercept queue, tamper / forge results, Reset"],
    ["Dockerfile, docker-compose.yml", "Optional container build and one-command run"],
], [2600, 6187])

# ---------------- CHAPTER 3
heading("CHAPTER 3. CORE IMPLEMENTATION AND CODE ANALYSIS", 1, page_break=True)
heading("3.1 Architecture and Actors", 2)
para("SecureChat models four roles. The sender owns a private key and signs messages. The channel is the server itself, "
     "which carries the signed message; because the server relays everything, it is also exactly where a man-in-the-middle "
     "sits, so the teacher's attacker tools act from here. The recipient verifies with the sender's public key. The admin "
     "(teacher) observes all accounts and messages and triggers the attacks. Figure 3.1 shows the normal flow and the "
     "attack flow.")
figure("fig00_architecture.png", "3.1", "Program flow. Top: a signed message delivered normally and verified as valid. Bottom: the teacher, acting as a man-in-the-middle, either edits the content (detected) or steals the key and re-signs (undetected).")
para("Technically the server (server/app.py) is a standard-library HTTP server that keeps all state in memory (server/"
     "state.py) behind a lock, and exposes one JSON endpoint per action: /api/join, /api/send and /api/state (polled by "
     "the chat every 1.5 seconds) for students, and /api/admin/login, /api/admin/state, /api/admin/hold, /api/admin/attack "
     "and /api/admin/reset for the teacher. Every signing and verifying call goes through the audited cryptography library "
     "(server/crypto.py), so the signature results shown to students are the genuine cryptographic outcome, not a "
     "simulation. Each message keeps two versions: what the sender typed and signed (orig_text), which the sender always "
     "sees, and what is delivered to the recipient (text and signature), which differs only if the teacher attacked it.")
heading("3.2 Key Code Snippets and Explanation", 2)
subhead("Snippet 1: Signing and verifying a message (server/crypto.py)")
code('''def sign(priv, text: str) -> bytes:
    """Sign the UTF-8 message, returning a DER-encoded signature."""
    return priv.sign(text.encode("utf-8"), ALGO)   # ECDSA with SHA-256

def verify(priv_or_pub, text: str, sig_der: bytes) -> bool:
    """True if sig_der is a valid signature of `text` under the key."""
    pub = (priv_or_pub.public_key() if hasattr(priv_or_pub, "public_key")
           else priv_or_pub)
    try:
        pub.verify(sig_der, text.encode("utf-8"), ALGO)
        return True
    except InvalidSignature:
        return False''')
para("Explanation: signing hashes the message with SHA-256 and signs the digest with the private key over curve P-256, "
     "exactly the ECDSA mechanism from our midterm report. Verification recomputes the hash and checks it against the "
     "signature using the public key. The signature is bound to the precise bytes of the message, so if a single character "
     "of the text changes, verify() returns False. The cryptography library chooses a safe per-signature nonce internally, "
     "so the signatures produced here are not vulnerable to the nonce-reuse weakness we studied earlier; the weakness this "
     "demo highlights instead is what happens when the whole private key is stolen.")
subhead("Snippet 2: Sending a signed message (server/state.py)")
code('''def send(self, token, to_uid, text):
    with self.lock:
        sender = self.user_by_token(token)
        if not sender:
            raise ValueError("session expired")
        ...                # recipient must exist and not be the sender
        text = (text or "").strip()[:MAX_TEXT]
        if not text:
            raise ValueError("empty message")
        der = crypto.sign(sender["priv"], text)   # sender's private key
        return self._new_message(sender["uid"], to_uid, text, der,
                                 "user", None, self.hold_mode)''')
para("Explanation: when a student sends a message, the server signs the exact text with that student's private key and "
     "stores it with its signature; _new_message() also records the honest verification result. If intercept mode "
     "(hold_mode) is on, the message is held in the queue and the recipient does not see it yet, while the sender sees it as "
     "waiting; otherwise it is delivered immediately. Empty messages, messages to oneself and requests from an unknown "
     "session are rejected.")
subhead("Snippet 3: Tampering versus forging a captured message (server/state.py)")
code('''if mode == "relay":
    if not base["held"]:
        raise ValueError("this message was already delivered")
    text, der = base["text"], base["sig_der"]
elif mode == "tamper":               # keep the ORIGINAL signature
    text, der = new_text, base["sig_der"]
else:                                # forge: re-sign, STOLEN key
    text, der = new_text, crypto.sign(sender["priv"], new_text)

if base["held"]:                     # in transit: delivered once
    self._deliver_held(base, text, der, mode)
    return base
# already delivered: an extra fake message in the sender's name
return self._new_message(base["from"], base["to"], text, der,
                         "attack", mode, held=False, injected=True)''')
para("Explanation: this is the heart of the demonstration. In tamper mode the attacker keeps the sender's original "
     "signature but delivers different text; because the signature no longer matches the text, the verification done in "
     "_deliver_held() or _new_message() (crypto.verify on the delivered text) returns False and the recipient sees an "
     "invalid signature. In forge mode the attacker uses the sender's private key, which the teacher has revealed (i.e. "
     "stolen), to produce a fresh, correct signature for the new text, so verification returns True and the recipient is "
     "fooled. A held message is modified in place and delivered once; an already-delivered message can only be used as a "
     "template for an extra fake message, which is marked injected and hidden from the real sender.")
heading("3.3 Reliability Measures for a Live Classroom", 2)
para("Testing with several phones at once revealed problems that would disturb a live demonstration. Table 3.1 lists each "
     "problem, its cause and the fix now in the code; every fix is covered by the automated tests in tests/test_state.py.")
table_caption("Table 3.1. Problems found in classroom testing and their fixes")
table(["Problem seen in testing", "Cause", "Fix in the code"], [
    ["A student's name appeared twice in the contact list", "A double tap, or Enter pressed while the Vietnamese keyboard was still composing, created two accounts", "One account per device (random device id kept by the browser); the join form ignores repeated submits and composing Enter; two students with the same name are shown as \"An\" and \"An 2\""],
    ["A message seemed not to arrive", "No notice when the conversation was not open; messages held by intercept mode stayed stuck after it was turned off", "Unread badges, a \"new message\" notice and a count in the tab title; turning intercept mode off delivers every held message unchanged"],
    ["A message appeared twice", "Enter fired twice; relaying an already-delivered message copied it; fake messages also showed on the real sender's phone", "One send at a time; relay only for held messages; injected fake messages are hidden from the real sender"],
    ["The sender saw the attacker's text as their own", "A held message was edited in place", "Each message keeps orig_text for the sender and text for the recipient"],
    ["The verification result vanished after a few seconds", "The page was redrawn on every update", "Verified message ids are remembered for the session"],
    ["The teacher's typing in the attack console was wiped", "The console was rebuilt on every 1.5-second update", "The queue and the message list are rebuilt only when their content changes; drafts are kept"],
    ["The teacher was logged out of the dashboard", "Each admin login replaced the single admin token", "Several admin sessions can be valid at once and survive Reset"],
], [2400, 2900, 3487])
heading("3.4 Cryptographic Components and Algorithms", 2)
table_caption("Table 3.2. Cryptographic components and algorithms")
table(["Component", "Where used", "Why we chose it"], [
    ["ECDSA over NIST P-256 with SHA-256", "Signing and verifying every message (crypto.py)", "The elliptic-curve signature from our midterm report; widely deployed (TLS, code signing), compact keys and signatures, directly supported by the audited library."],
    ["SHA-256 (FIPS 180-4)", "The message digest inside every signature", "Collision-resistant 256-bit hash matching the P-256 order; a change of one character changes the digest completely, which is why tampering is detected."],
    ["cryptography library key generation (CSPRNG)", "A key pair per account", "Audited, constant-time primitives and a safe internal nonce per signature, so the app itself is not vulnerable to the implementation bugs we studied."],
    ["DER signature encoding (r, s)", "Storing and displaying signatures", "Standard ECDSA signature encoding; the r value is shown on screen so the audience can see the signature change when a message is re-signed."],
    ["HTTP + JSON (standard library)", "Transport between phones and the server", "Zero extra dependencies, works in any browser; one endpoint per action keeps the code easy to read during the demo."],
], [2500, 2400, 3887])
table_caption("Table 3.3. Attack actions in the teacher dashboard")
table(["Action (button)", "What the attacker does", "Recipient's check"], [
    ["✏️ Sửa, giữ chữ ký cũ (tamper)", "Changes the content of a held message, keeps the sender's original signature", "INVALID — tampering detected (integrity holds)"],
    ["🔑 Sửa + ký lại (forge)", "Changes the content and re-signs it with the stolen private key", "VALID — the forgery is accepted (recipient fooled)"],
    ["➡️ Chuyển nguyên (relay)", "Delivers a held message unchanged (also done automatically when intercept mode is turned off)", "VALID — a normal delivery"],
    ["📨 Giả mạo tin mới (inject)", "Sends an extra message in a sender's name, based on a delivered one, with the old signature or re-signed", "INVALID with the old signature; VALID if re-signed with the stolen key"],
], [2500, 3800, 2487])

# ---------------- CHAPTER 4
heading("CHAPTER 4. STEP-BY-STEP DEMONSTRATION WALKTHROUGH", 1, page_break=True)
para("The teacher starts the server (python3 run.py --passcode 123456, or docker compose up), projects the admin "
     "dashboard, and shows the QR code. The steps below follow the three steps required by the course template: "
     "initialization, the attack, and the result.")
heading("4.1 Step 1: Initialization", 2)
para("The teacher opens the dashboard and enters the admin passcode. Students scan the QR code (Figure 4.1), type a name, "
     "and each receives an ECDSA key pair and a chat screen; joining twice from the same phone keeps a single account. "
     "Accounts and messages appear live on the dashboard (Figure 4.2): the accounts with their private keys blurred on the "
     "left, the full message feed in the middle, and the intercept queue and fake-message console on the right. At this "
     "point everything is normal: a student signs a message, the recipient presses Kiểm tra chữ ký and sees HỢP LỆ (valid), "
     "confirming that correctly signed messages are accepted.")
figure("fig01_join.png", "4.1", "The join page. A student scans the QR code, types a name, and immediately receives an ECDSA key pair.", 5.6)
figure("fig03_admin.png", "4.2", "The teacher dashboard: QR code and accounts (private keys blurred) on the left, the live feed in the middle (an altered message shows its original text struck through), and on the right the intercept queue holding one message plus the fake-message console.", 6.2)
heading("4.2 Step 2: Execution / The Attack", 2)
para("The teacher turns on Chế độ chặn tin (intercept mode). From now on, a message a student sends is held in Hàng đợi "
     "chặn (the intercept queue) instead of reaching the recipient, and the sender sees it as ⏳ đang chờ chuyển (waiting) "
     "with exactly the text they typed (Figure 4.3). On a held message the teacher types new content, for example changing "
     "200,000 VND to 2,000,000 VND, and presses Sửa, giữ chữ ký cũ (tamper): the new text is delivered with the sender's "
     "original signature. For the stronger attack the teacher first clicks the sender's blurred private key to reveal it, "
     "which plays the role of the attacker stealing the key, then edits the next held message (50,000 VND to 5,000,000 VND) "
     "and presses Sửa + ký lại (forge), which re-signs the new text with that key. Each held message reaches the "
     "recipient exactly once. Optionally, Giả mạo tin mới sends an extra fake message in a student's name.")
figure("fig04_chat_sender.png", "4.3", "The sender's view. The sender still sees what they actually typed (200,000 VND and 50,000 VND), not the attacker's version; the last message is held in the intercept queue (⏳ đang chờ chuyển).", 6.0)
heading("4.3 Step 3: Verification / The Result", 2)
para("The recipient presses Kiểm tra chữ ký on each message (Figures 4.4 and 4.5). The honest signature check gives two "
     "clearly different outcomes. The message altered with the original signature is reported as KHÔNG HỢP LỆ (invalid): "
     "the recipient knows the content was changed, so integrity is preserved. The message re-signed with the stolen key is "
     "reported as HỢP LỆ (valid): the recipient cannot tell it apart from a genuine message, so once the private key leaks, "
     "integrity, authentication and non-repudiation all collapse. The message still in the queue has not reached the "
     "recipient at all. Seeing an altered amount rejected in one case and accepted in the other, depending only on whether "
     "the key was stolen, is the lesson the demonstration is built to deliver.")
figure("fig02_chat_recipient.png", "4.4", "The recipient's chat. The genuine message is valid; the message altered in transit with the original signature (2,000,000 VND) is invalid; the message re-signed with the stolen key (5,000,000 VND) is valid and fools the recipient. A red badge shows an unread message from another student.", 6.0)
figure("fig05_mobile.png", "4.5", "The same conversation on a phone: the conversation opens as its own screen with a back button to the contact list.", 2.7)

# ---------------- CHAPTER 5
heading("CHAPTER 5. DEFENSE MECHANISM AND RESIDUAL RISKS", 1, page_break=True)
heading("5.1 What the Signature Already Defends", 2)
para("The digital signature itself is the defense against tampering. Because the signature is bound to the exact bytes of "
     "the message, any change to the content while it is in transit makes verification fail, as the Tamper case shows. An "
     "attacker who controls the channel but does not hold the private key therefore cannot forge an acceptable message; the "
     "best they can do is corrupt messages, which the recipient detects and rejects. This is integrity and authentication "
     "working as intended, and it needs no extra mechanism beyond verifying every message, which SecureChat does.")
heading("5.2 The Real Vulnerability: Private-Key Theft", 2)
para("The Forge case shows that the whole guarantee rests on one assumption: the private key stays secret. Once the key "
     "leaks, the attacker can produce signatures that are mathematically indistinguishable from the owner's, so no verifier "
     "can catch the forgery. Defending the system therefore means defending the key, not adding more signature checks. In "
     "practice this means: never expose or transmit the private key (SecureChat keeps each key on the server and never "
     "sends it to other clients; revealing one on the dashboard is only a teaching action); store keys in encrypted form or "
     "in a hardware security module, TPM or cloud KMS so they cannot be read even if the host is compromised; and limit who "
     "and what can use the key.")
para("Two further controls protect the surrounding system. First, the message channel should run over TLS, so that a "
     "network attacker cannot even read or edit traffic in transit; our classroom build runs over plain HTTP on the local "
     "network for simplicity, which is itself a useful point to discuss. Second, public keys must be distributed "
     "authentically through a PKI with certificate validation and revocation, otherwise an attacker could substitute their "
     "own public key and have their messages accepted as someone else's.")
heading("5.3 How an Attacker Might Still Succeed", 2)
bullet("**Endpoint compromise:** malware on the sender's device can read the private key straight from memory or storage, bypassing every network defense. Full-disk encryption, OS hardening and keys held in a secure enclave reduce this risk.")
bullet("**Stolen or weak key storage:** an unencrypted key file, a leaked backup or an insider can hand the key to an attacker. Encrypt keys at rest, use an HSM or KMS, and log every use of the key.")
bullet("**Unauthenticated public keys:** if the recipient trusts a public key delivered over an unauthenticated channel, the attacker can swap in their own key. A PKI with chain validation and revocation (CRL/OCSP) is required.")
bullet("**No transport security:** over plain HTTP a man-in-the-middle can read and alter traffic freely (tampering is still caught by the signature, but metadata and message contents are exposed). TLS closes this gap.")
bullet("**Social engineering:** the strongest cryptography fails if a user is tricked into signing or approving a malicious message. User training and clear confirmation screens help.")

# ---------------- CHAPTER 6
heading("CHAPTER 6. CONCLUSION AND LIMITATIONS", 1, page_break=True)
heading("6.1 Conclusion", 2)
para("SecureChat turns the midterm theory into a live classroom experience. Every message is really signed and verified "
     "with ECDSA through an audited library, so the audience sees genuine results. The demonstration makes two points "
     "concrete: tampering with a signed message is always detected, and a stolen private key lets an attacker forge "
     "messages that no verifier can catch. Together they reinforce the midterm conclusion that the security of a signature "
     "scheme in practice depends far more on correct implementation and careful key handling than on the algorithm itself.")
heading("6.2 Hardest Technical Challenges", 2)
bullet("**Keeping the demo honest.** The recipient's verification uses the same audited library a real client would, and the attack results are computed, not scripted, so the valid/invalid outcomes are real.")
bullet("**Making it reliable on real phones.** Double taps, Vietnamese keyboards that send Enter while still composing, and a page that redraws every 1.5 seconds caused duplicate accounts, duplicate or missing messages and vanishing results. Table 3.1 lists each problem and its fix, and 16 automated tests now guard against them.")
bullet("**Separating what each side sees.** For the lesson to be convincing, the sender must keep seeing what they typed while the recipient sees the attacker's version, and a fake message must not appear on the real sender's phone; this required storing the original and the delivered version of every message.")
bullet("**Making the cryptography visible.** The r value of each signature is shown so the audience can see that a re-signed message carries a new signature while a tampered one keeps the old one.")
heading("6.3 Limitations", 2)
bullet("The classroom build runs over plain HTTP on the local network and has no transport encryption; it is a teaching tool, not a secure messenger.")
bullet("Private keys are generated and held on the server for the demonstration and can be revealed by the admin on purpose; a real system would never expose a private key.")
bullet("State is kept in memory only, so all data is lost (by design) when the server stops; there is no persistence or account recovery.")
bullet("An account is tied to one browser on one device, so two students sharing a phone in the same browser share an account.")
bullet("The browser asks the server for updates every 1.5 seconds, which is fine for a classroom but not tuned for large-scale use, and there is no rate limiting beyond the admin passcode.")
heading("6.4 Improvements for a Real-World Production Environment", 2)
para("Run every connection over TLS; keep private keys in an HSM, TPM or cloud KMS and never expose them; distribute public "
     "keys through a PKI with certificate validation and revocation; add persistent storage, authentication and rate "
     "limiting; and use a real-time transport such as WebSockets instead of polling. For the signatures themselves, keep "
     "using an audited, constant-time library, and consider Ed25519, which is deterministic by design, or a move to "
     "post-quantum signatures (ML-DSA, FIPS 204) for long-term security.")

# ---------------- REFERENCES
heading("REFERENCES", 1, page_break=True)
refs = [
    '[1] National Institute of Standards and Technology, "Digital Signature Standard (DSS)," FIPS PUB 186-5, Feb. 2023.',
    '[2] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, Aug. 2015.',
    '[3] Certicom Research, "SEC 2: Recommended Elliptic Curve Domain Parameters," v2.0, 2010. P-256 (secp256r1) parameters.',
    '[4] Python Cryptographic Authority, "cryptography documentation: Elliptic Curve Signing / Verification." [Online]. Available: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/',
    '[5] Python Software Foundation, "http.server — HTTP servers," Python 3 documentation. [Online]. Available: https://docs.python.org/3/library/http.server.html',
    '[6] L. Simon, "segno: Python QR Code and Micro QR Code encoder." [Online]. Available: https://segno.readthedocs.io/',
    '[7] E. Rescorla, "The Transport Layer Security (TLS) Protocol Version 1.3," RFC 8446, IETF, Aug. 2018.',
    '[8] OWASP Foundation, "Cryptographic Storage Cheat Sheet," OWASP Cheat Sheet Series, 2023.',
    '[9] D. Boneh and V. Shoup, A Graduate Course in Applied Cryptography, v0.6, Stanford University, 2023. [Online]. Available: https://toc.cryptobook.us/',
    '[10] Trieu Ngoc Van Anh, Duong Tran Quoc Khanh and Nguyen Vo Thanh Tu, "Digital Signatures in Practice: RSA and ECC, the Role of Hash Functions, and the Guarantee of Non-Repudiation," Midterm Report, Ton Duc Thang University, 2026.',
]
for r_ in refs:
    p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', after=120, line=360, lineRule='auto')
    sub(pPr, 'w:ind', left=567, hanging=567); sub(pPr, 'w:jc', val='both')
    run(p, r_); put(p)
p = E('w:p'); pPr = sub(p, 'w:pPr'); sub(pPr, 'w:spacing', before=240, after=120, line=360, lineRule='auto'); sub(pPr, 'w:jc', val='both')
run(p, "AI assistance attribution: ", b=True)
run(p, "The group used Claude (Anthropic), an AI assistant, to help build the SecureChat application (server and web "
       "interface), capture the screenshots, and draft this report. The group reviewed, ran and tested all code and is "
       "responsible for the final content. The cryptographic operations use the audited cryptography library, and the "
       "ECDSA and SHA-256 mechanisms follow references [1]–[3].")
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
          ("3.1", "Problems found in classroom testing and their fixes"), ("3.2", "Cryptographic components and algorithms"),
          ("3.3", "Attack actions in the teacher dashboard")]
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

d.core_properties.title = "Final Report - SecureChat Digital Signature Demo (N05_G05)"
d.save(OUT)
json.dump({"toc": [t for _, t, _ in TOC_ENTRIES], "figs": [f"Figure {n}." for n, _ in FIGS],
           "tabs": [f"Table {n}." for n, _ in TABLES]}, open(OUT + '.keys.json', 'w'), indent=1)
print("saved", OUT, len(TOC_ENTRIES), "toc entries,", len(FIGS), "figures")
