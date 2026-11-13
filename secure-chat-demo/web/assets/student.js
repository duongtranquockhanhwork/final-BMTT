/* shared helpers for the student and admin pages */
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
/* "Nguyễn Văn An" -> "NA", "Bob" -> "BO" */
function initials(n) {
  const w = String(n || '?').trim().split(/\s+/);
  const s = w.length > 1 ? w[0][0] + w[w.length - 1][0] : w[0].slice(0, 2);
  return s.toUpperCase();
}
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
}
function toast(m, kind) {
  const e = document.getElementById('toast'); if (!e) return alert(m);
  e.textContent = m; e.className = 'toast ' + (kind || ''); e.style.display = 'block';
  clearTimeout(e._t); e._t = setTimeout(() => e.style.display = 'none', 3500);
}
/* One random id per browser, kept across "Leave", so joining twice from the
   same phone reuses the same account instead of creating a duplicate. */
function deviceId() {
  let id = localStorage.getItem('sc_device');
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
    localStorage.setItem('sc_device', id);
  }
  return id;
}
/* Enter while an IME (e.g. Vietnamese Telex) is still composing must not submit. */
function isEnter(e) { return e.key === 'Enter' && !e.isComposing && e.keyCode !== 229; }

/* Map server error codes to Vietnamese messages for the UI. */
const ERR_VI = {
  'session expired': 'Phiên đã hết hạn (server vừa khởi động lại). Hãy tham gia lại.',
  'unknown recipient': 'Người nhận không còn tồn tại.',
  'cannot message yourself': 'Không thể tự nhắn cho chính mình.',
  'empty message': 'Tin nhắn trống.',
  'wrong passcode': 'Sai mã admin.',
  'admin only': 'Phiên admin đã hết hạn, hãy đăng nhập lại.',
  'message not found': 'Không tìm thấy tin nhắn.',
  'this message was already delivered': 'Tin này đã được giao rồi, không thể chuyển lại.',
  'enter the new (fake) content': 'Hãy nhập nội dung giả mạo.',
};
async function api(path, body = {}) {
  let r;
  try {
    r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch (e) {
    const err = new Error('Mất kết nối tới server'); err.network = true; throw err;
  }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const err = new Error(ERR_VI[j.error] || j.error || ('HTTP ' + r.status)); err.code = j.error; err.status = r.status; throw err; }
  return j;
}
