from __future__ import annotations
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_master_key() -> bytes:
    key_b64 = os.environ.get("LAKEMIND_MASTER_KEY", "")
    if not key_b64:
        raise ValueError("LAKEMIND_MASTER_KEY not set")
    raw = base64.b64decode(key_b64)
    if len(raw) != 32:
        raise ValueError("master key must be 32 bytes (base64-encoded)")
    return raw


def encrypt(plaintext: str, aad: bytes = b"") -> bytes:
    key = _get_master_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    ct = aesgcm.encrypt(iv, plaintext.encode(), aad)
    return iv + ct


def decrypt(ciphertext: bytes, aad: bytes = b"") -> str:
    key = _get_master_key()
    aesgcm = AESGCM(key)
    iv = ciphertext[:12]
    ct = ciphertext[12:]
    plaintext = aesgcm.decrypt(iv, ct, aad)
    return plaintext.decode()
