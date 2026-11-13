"""
qr.py - render the classroom join URL as a QR code (SVG).

Uses `segno` (pure-Python, zero dependencies) when available. If it is not
installed, qr_svg() returns None and the admin page shows the URL as large text
for students to type instead.
"""

import io


def qr_svg(data: str):
    try:
        import segno
    except Exception:
        return None
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", scale=7, border=3, dark="#1d2433")
    return buf.getvalue().decode("utf-8")
