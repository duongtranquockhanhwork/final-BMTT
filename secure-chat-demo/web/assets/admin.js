/* Teacher dashboard: live view of all accounts and messages, plus the
   attacker console used to demonstrate tampering and key theft. */
let ATOKEN = localStorage.getItem('sc_admin') || null;
let lastEvent = -1, users = [], messages = [], holdMode = false, started = false, polling = false;
const revealed = {};          // uid -> private key shown
const drafts = {};            // held message id -> fake text being typed in the queue
let queueSig = '', targetSig = '';

async function login() {
  const pass = document.getElementById('pass').value.trim();
  if (!pass) return toast('Nhập mã admin');
  const b = document.getElementById('loginBtn'); b.disabled = true;
  try {
    const r = await api('/api/admin/login', { passcode: pass });
    ATOKEN = r.token; localStorage.setItem('sc_admin', ATOKEN);
    start();
  } catch (e) { toast(e.message, 'bad'); }
  finally { b.disabled = false; }
}

function logout(msg) {
  localStorage.removeItem('sc_admin'); ATOKEN = null; started = false;
  document.getElementById('dash').style.display = 'none';
  document.getElementById('login').style.display = 'block';
  if (msg) toast(msg, 'bad');
}

async function start() {
  if (started) return;
  started = true;
  document.getElementById('login').style.display = 'none';
  document.getElementById('dash').style.display = 'block';
  try {
    const info = await (await fetch('/api/info')).json();
    document.getElementById('joinUrl').textContent = info.base_url;
    document.getElementById('qrImg').innerHTML = info.has_qr
      ? '<img src="/qr" alt="QR">'
      : '<div class="small-muted">Cài <code>segno</code> để hiện mã QR. Sinh viên mở URL ở dưới.</div>';
  } catch (e) { /* QR is optional */ }
  await poll(true);
}

async function poll(force) {
  if (!ATOKEN || (polling && !force)) return;
  polling = true;
  try {
    const snap = await api('/api/admin/state', { token: ATOKEN });
    if (!force && snap.event === lastEvent) return;
    lastEvent = snap.event; users = snap.users; messages = snap.messages; holdMode = snap.hold_mode;
    render();
  } catch (e) {
    if (e.status === 401) logout('Phiên admin đã hết hạn (server khởi động lại). Hãy đăng nhập lại.');
  } finally { polling = false; }
}

function uName(uid) { const u = users.find(x => x.uid === uid); return u ? u.name : '?'; }
function uColor(uid) { const u = users.find(x => x.uid === uid); return u ? u.color : '#888'; }
function av(uid) { return `<span class="avatar sm" style="background:${uColor(uid)}">${esc(initials(uName(uid)))}</span>`; }

function render() {
  document.getElementById('uCount').textContent = `(${users.length})`;
  document.getElementById('mCount').textContent = `(${messages.length})`;
  document.getElementById('holdSw').classList.toggle('on', holdMode);
  const hs = document.getElementById('holdState');
  hs.textContent = holdMode ? 'ĐANG BẬT' : 'tắt'; hs.className = 'pill ' + (holdMode ? 'warn' : '');

  // accounts + blurred private keys
  document.getElementById('users').innerHTML = users.length
    ? users.map(u => `<div class="urow">${av(u.uid)}<b>${esc(u.name)}</b><span class="grow"></span>
        <span class="key ${revealed[u.uid] ? '' : 'blur'}" title="Bấm để hiện/ẩn khóa bí mật" onclick="toggleKey(${u.uid})">🔑 ${esc(u.d.slice(0, 10))}…${esc(u.d.slice(-6))}</span></div>`).join('')
    : '<div class="small-muted" style="padding:6px">Chưa có ai tham gia.</div>';

  // live feed (newest at the bottom)
  const feed = document.getElementById('feed');
  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
  feed.innerHTML = messages.length ? messages.map(m => {
    let tag;
    if (m.held) tag = '<span class="pill warn">⏸ đang giữ</span>';
    else if (m.attack_mode === 'tamper') tag = '<span class="pill bad">✏️ đã sửa · chữ ký KHÔNG hợp lệ</span>';
    else if (m.attack_mode === 'forge') tag = '<span class="pill bad">🔑 giả mạo · chữ ký HỢP LỆ (bị lừa)</span>';
    else tag = m.valid ? '<span class="pill good">✔ hợp lệ</span>' : '<span class="pill bad">⚠ không hợp lệ</span>';
    const fake = m.injected ? ' <span class="pill bad">tin giả mới</span>' : '';
    const changed = !m.injected && m.text !== m.orig_text ? `<div class="was">Gốc: ${esc(m.orig_text)}</div>` : '';
    return `<div class="fmsg ${m.origin === 'attack' ? 'attack' : ''} ${m.held ? 'held' : ''}">
      <div class="top">${av(m.from)}<b>${esc(m.fromName)}</b><span class="arrow">→</span>${av(m.to)}<span>${esc(m.toName)}</span><span class="grow"></span><span class="small-muted">${fmtTime(m.ts)} · #${m.id}</span></div>
      <div class="text">${esc(m.text)}</div>${changed}
      <div class="foot">r=${esc(m.r)}… ${tag}${fake}</div></div>`;
  }).join('') : '<div class="small-muted">Chưa có tin nhắn nào.</div>';
  if (atBottom) feed.scrollTop = feed.scrollHeight;

  renderQueue();
  renderTarget();
}

/* The queue and the select contain inputs, so they are rebuilt only when their
   content changes; typed text and the open dropdown are never wiped by polling. */
function renderQueue() {
  const held = messages.filter(m => m.held);
  document.getElementById('qCount').textContent = held.length ? `(${held.length})` : '';
  const sig = held.map(m => m.id).join(',') + '|' + holdMode;
  if (sig === queueSig) return;
  queueSig = sig;
  const box = document.getElementById('queue');
  const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.qid : null;
  box.innerHTML = held.length ? held.map(m => `<div class="qcard">
      <div class="top">${av(m.from)}<b>${esc(m.fromName)}</b><span class="arrow">→</span>${av(m.to)}<span>${esc(m.toName)}</span><span class="grow"></span><span class="small-muted">#${m.id}</span></div>
      <div class="orig">${esc(m.orig_text)}</div>
      <input type="text" data-qid="${m.id}" placeholder="Nội dung giả mạo (để trống nếu chuyển nguyên)" maxlength="500" value="${esc(drafts[m.id] || '')}" oninput="drafts[${m.id}]=this.value">
      <div class="acts">
        <button class="qa-relay" onclick="release(${m.id},'relay')">➡️ Chuyển nguyên</button>
        <button class="qa-tamper" onclick="release(${m.id},'tamper')">✏️ Sửa, giữ chữ ký cũ</button>
        <button class="qa-forge" onclick="release(${m.id},'forge')">🔑 Sửa + ký lại</button>
      </div></div>`).join('')
    : `<div class="small-muted">${holdMode ? 'Đang chờ tin nhắn mới… Khi sinh viên gửi, tin sẽ hiện ở đây.' : 'Bật “Chế độ chặn tin” để giữ tin nhắn lại và sửa trước khi tới người nhận.'}</div>`;
  if (focused) { const el = box.querySelector(`[data-qid="${focused}"]`); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }
}

function renderTarget() {
  const sel = document.getElementById('target');
  const opts = messages.filter(m => !m.held && !m.injected);
  const sig = opts.map(m => m.id + ':' + m.fromName + ':' + m.toName).join(',');
  if (sig === targetSig || document.activeElement === sel) return;
  targetSig = sig;
  const cur = sel.value;
  sel.innerHTML = opts.length
    ? opts.slice().reverse().map(m => `<option value="${m.id}">#${m.id} ${esc(m.fromName)} → ${esc(m.toName)}: ${esc(m.orig_text.slice(0, 30))}${m.orig_text.length > 30 ? '…' : ''}</option>`).join('')
    : '<option value="">(chưa có tin nào đã giao)</option>';
  if (cur && opts.some(m => String(m.id) === cur)) sel.value = cur;   // otherwise newest is first
}

function toggleKey(uid) { revealed[uid] = !revealed[uid]; render(); }

async function toggleHold() {
  const held = messages.filter(m => m.held).length;
  try {
    const r = await api('/api/admin/hold', { token: ATOKEN, on: !holdMode });
    holdMode = r.hold_mode;
    toast(holdMode ? 'Đã bật chặn tin: tin mới sẽ bị giữ lại' : (held ? `Đã tắt chặn tin, chuyển nguyên ${held} tin đang giữ` : 'Đã tắt chặn tin'), 'info');
    poll(true);
  } catch (e) { if (e.status === 401) logout(e.message); else toast(e.message, 'bad'); }
}

async function release(mid, mode) {
  const text = (drafts[mid] || '').trim();
  if (mode !== 'relay' && !text) return toast('Nhập nội dung giả mạo vào ô của tin này', 'bad');
  try {
    const r = await api('/api/admin/attack', { token: ATOKEN, message_id: mid, new_text: text, mode });
    delete drafts[mid];
    toast(mode === 'relay' ? 'Đã chuyển nguyên tin nhắn' :
          r.valid ? 'Đã chuyển · chữ ký HỢP LỆ (người nhận sẽ bị lừa)' : 'Đã chuyển · chữ ký KHÔNG hợp lệ (sẽ bị phát hiện)', r.valid ? 'info' : 'good');
    poll(true);
  } catch (e) { if (e.status === 401) logout(e.message); else toast(e.message, 'bad'); }
}

async function inject() {
  const mid = document.getElementById('target').value;
  if (!mid) return toast('Chưa có tin nhắn nào đã giao để làm mẫu', 'bad');
  const mode = document.querySelector('input[name=mode]:checked').value;
  const newText = document.getElementById('newText').value.trim();
  if (!newText) return toast('Nhập nội dung giả mạo', 'bad');
  const b = document.getElementById('injectBtn'); b.disabled = true;
  try {
    const r = await api('/api/admin/attack', { token: ATOKEN, message_id: mid, new_text: newText, mode });
    toast(r.valid ? 'Đã gửi tin giả · chữ ký HỢP LỆ (người nhận sẽ bị lừa)' : 'Đã gửi tin giả · chữ ký KHÔNG hợp lệ (sẽ bị phát hiện)', r.valid ? 'info' : 'good');
    document.getElementById('newText').value = '';
    poll(true);
  } catch (e) { if (e.status === 401) logout(e.message); else toast(e.message, 'bad'); }
  finally { b.disabled = false; }
}

async function resetAll() {
  if (!confirm('Xóa toàn bộ tài khoản, khóa và tin nhắn?')) return;
  try {
    await api('/api/admin/reset', { token: ATOKEN });
    for (const k in revealed) delete revealed[k];
    for (const k in drafts) delete drafts[k];
    queueSig = targetSig = '';
    toast('Đã xóa toàn bộ dữ liệu', 'good');
    poll(true);
  } catch (e) { if (e.status === 401) logout(e.message); else toast(e.message, 'bad'); }
}

document.getElementById('pass').addEventListener('keydown', e => { if (isEnter(e)) login(); });
document.getElementById('holdSw').addEventListener('keydown', e => { if (e.key === ' ' || isEnter(e)) { e.preventDefault(); toggleHold(); } });
setInterval(poll, 1500);
// automation helper for screenshots/bookmarks (localhost): #pc=<passcode>
const _hp = location.hash.match(/pc=(\d+)/);
if (_hp) { localStorage.removeItem('sc_admin'); ATOKEN = null; document.getElementById('pass').value = _hp[1]; login(); }
else if (ATOKEN) start();
