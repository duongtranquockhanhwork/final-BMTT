# SecureChat — Classroom Digital-Signature Demo

An interactive, multi-user web app for a live classroom demonstration of digital
signatures. Students scan a QR code, type a name, and message each other. Every
message is signed with the sender's ECDSA key and can be verified by the recipient.

The teacher (admin) sees the whole flow live and plays the attacker to show the two
core lessons from our midterm theory report:

1. **Tampering is detected** — if the content of a signed message is changed in
   transit, the recipient's signature check fails (**integrity**).
2. **A stolen private key breaks everything** — if the attacker steals the private
   key, they can change the content *and* re-sign it, so the forgery still verifies
   and the recipient is fooled (**why protecting the private key matters**).

> ⚠️ **Educational use only.** This is a teaching tool for a consenting classroom.
> All accounts, keys and messages are created by the app for the demo, kept in
> memory only, and wiped when the server stops or the teacher presses **Reset**.
> It is not a secure messenger and must not be used for real private communication.

## Requirements
* **Option A:** Python 3.10+ (on macOS/Linux the command is `python3`), with
  `cryptography >= 44` and `segno >= 1.6` (QR code; optional — without it the join
  URL is shown as text): `pip install -r requirements.txt`
* **Option B:** Docker with Compose (nothing else to install).

## Run — Option A: Python
```bash
python3 run.py --passcode 123456
```
The console prints the **join URL** students open, the **teacher dashboard** URL and
the **ADMIN PASSCODE**. Without `--passcode` a new random 6-digit code is generated
**every time the server starts**, so always read the current one from the console.

Other options: `--port 9000`, `--host 127.0.0.1` (local only, no phones),
`--public-host <ip>` (address printed in the join URL / QR), `--open` (open the
dashboard in a browser).

## Run — Option B: Docker
1. Open `docker-compose.yml` and set `SC_PUBLIC_HOST` to your laptop's Wi-Fi IP so
   the join URL and QR are reachable from phones (`ipconfig getifaddr en0` on macOS,
   `hostname -I` on Linux). Change `SC_ADMIN_PASSCODE` if you like (default `123456`).
2. Start it:
   ```bash
   docker compose up --build -d
   ```
3. Open `http://<your-ip>:8070/admin` (or `http://127.0.0.1:8070/admin` on the
   laptop itself). Stop with `docker compose down`; all data is wiped.

Without Compose:
```bash
docker build -t securechat-demo .
docker run -d --name securechat -p 8070:8070 -e SC_ADMIN_PASSCODE=123456 -e SC_PUBLIC_HOST=<your-ip> securechat-demo
```

The laptop and the phones must be on the **same Wi-Fi network**, and the laptop
firewall must allow incoming connections on port 8070.

## What students see
* **Join:** type a name and tap *Tham gia*. Tapping twice, pressing Enter while the
  Vietnamese keyboard is still composing, or leaving and joining again from the same
  phone all reuse **one** account (the phone keeps a random device id). If two
  different students pick the same name, the second becomes e.g. `An 2`.
* **Chat:** conversations are sorted by the latest message and show a preview; new
  messages raise a red **unread badge**, a "Tin nhắn mới từ …" notice and a count in
  the tab title. On a phone the list and the conversation are separate screens with
  a back button. Your own messages show `✓ đã gửi`, or `⏳ đang chờ chuyển` while
  the teacher holds them.
* **Verify:** each received message has a **🔍 Kiểm tra chữ ký** button. The result
  (**HỢP LỆ** or **KHÔNG HỢP LỆ — nội dung đã bị thay đổi!**) stays on screen.
* A sender always sees **what they typed**, even if the teacher altered the copy the
  recipient received, and never sees the fake messages the teacher sends in their name.

## How to run the demo in class
1. Start the server, open the **dashboard**, enter the passcode, and project it.
2. Students **scan the QR code**, type a name and chat. Accounts and messages appear
   live in the dashboard; private keys are blurred (click one to reveal it).
3. **Intercept a message (main demo).** Turn on **Chế độ chặn tin**. New messages are
   now held in **Hàng đợi chặn** instead of being delivered. On a held message,
   type fake content and choose:
   * **✏️ Sửa, giữ chữ ký cũ** — delivered with the original signature → the
     recipient's check says **KHÔNG HỢP LỆ** (tampering caught);
   * **🔑 Sửa + ký lại** — first reveal the sender's private key ("steal" it); the
     new text is re-signed with it → the check says **HỢP LỆ** (recipient fooled);
   * **➡️ Chuyển nguyên** — deliver unchanged.
   The recipient receives each held message **exactly once**. Turning interception
   off delivers any message still in the queue unchanged, so nothing gets stuck.
4. **Send a new fake message (optional).** In **Giả mạo tin mới**, pick a message
   that was already delivered, type new content and send it as an *extra* message
   in the same sender's name, either with the old signature (caught) or signed with
   the stolen key (accepted).
5. When finished, press **🗑️ Xóa toàn bộ dữ liệu** (or stop the server).

## How it works
* Each account gets a real **ECDSA P-256 / SHA-256** key pair from the audited
  `cryptography` library (`server/crypto.py`).
* Sending signs the exact text with the sender's private key. The recipient's check
  verifies that text and signature against the sender's public key — the genuine
  cryptographic result, computed on the server.
* The server is the channel, which is also the attacker's position
  (`server/state.py`). Each message keeps two versions: what the sender signed
  (`orig_text`) and what is delivered (`text` + signature):
  * **tamper** delivers new text with the *original* signature → verification fails;
  * **forge** re-signs the new text with the sender's (stolen) key → verification passes.
* Everything is in memory; ids and the polling counter keep increasing across Reset
  so open browsers never confuse old and new data.

## Tests
```bash
python3 -m unittest discover -s tests -v
```
16 automated checks cover joining (no duplicates, unique names), delivery, the
intercept queue, tamper/forge results, what each side sees, and Reset.

## Troubleshooting
* **Cannot log into the admin page** — use the passcode of the server instance that
  is running now (fix it with `--passcode` or `SC_ADMIN_PASSCODE`). Several admin
  tabs can be logged in at the same time.
* **A message does not arrive** — check whether *Chế độ chặn tin* is on: held
  messages reach the recipient only after you release them (or turn it off).
* **Students are sent back to the join page** — the server was restarted or Reset was
  pressed; their old session no longer exists, so they simply join again.

## Project layout
```
run.py                 entry point: starts the server, prints join URL + admin passcode
requirements.txt
Dockerfile             container image for the app
docker-compose.yml     one-command run; set SC_PUBLIC_HOST + SC_ADMIN_PASSCODE here
server/
  crypto.py            ECDSA P-256 sign/verify (cryptography library)
  state.py             in-memory accounts + messages, intercept queue, attack logic
  app.py               HTTP routing and the JSON API
  qr.py                QR code (segno) for the join URL
web/
  join.html            student: create an account with a name
  chat.html            student: conversations, unread badges, verify button
  admin.html           teacher: dashboard, intercept queue, fake-message console
  assets/style.css, student.js (shared helpers), admin.js
tests/test_state.py    automated regression tests
screenshots/           images used in the report
report/                the final technical report (build with report/make_report.sh)
```

## Notes on safety and privacy
* The admin dashboard is protected by a passcode printed only in the server console.
* Every page carries a banner saying this is an educational demo and that data is
  wiped afterwards, so participants know the teacher is simulating an attack.
* Private keys are generated by the app for the demo only; revealing one on the
  dashboard is a teaching action ("the attacker stole the key").
* The `#pc=` (admin) and `#t=` (chat) URL fragments are optional shortcuts used for
  screenshots; they only prefill a value you must already know and never bypass the
  server's checks.
