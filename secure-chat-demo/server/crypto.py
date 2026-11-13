"""
crypto.py - ECDSA (NIST P-256 / SHA-256) signing helpers, using the audited
`cryptography` library. Each account gets a real ECDSA key pair; messages are
signed by the sender and verified by the recipient.

This mirrors the theory from the group's midterm report: a signature proves the
message came from the holder of the private key and was not altered. If the
private key leaks, an attacker can forge messages that still verify.
"""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

ALGO = ec.ECDSA(hashes.SHA256())


def generate_keypair():
    """Return a fresh ECDSA P-256 private key object (holds the public key too)."""
    return ec.generate_private_key(ec.SECP256R1())


def private_value(priv) -> int:
    """The secret scalar d. Shown (blurred) only for the teaching demo."""
    return priv.private_numbers().private_value


def public_xy(priv):
    n = priv.public_key().public_numbers()
    return n.x, n.y


def sign(priv, text: str) -> bytes:
    """Sign the UTF-8 message, returning a DER-encoded signature."""
    return priv.sign(text.encode("utf-8"), ALGO)


def verify(priv_or_pub, text: str, sig_der: bytes) -> bool:
    """True if sig_der is a valid signature of `text` under the given key's public half."""
    pub = priv_or_pub.public_key() if hasattr(priv_or_pub, "public_key") else priv_or_pub
    try:
        pub.verify(sig_der, text.encode("utf-8"), ALGO)
        return True
    except InvalidSignature:
        return False


def rs(sig_der: bytes):
    """Decode a DER signature into its two integer components (r, s), for display."""
    try:
        return decode_dss_signature(sig_der)
    except Exception:
        return (0, 0)


def hx(n: int, width: int = 64) -> str:
    return f"{n:0{width}x}"
