from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretCrypto:
    def __init__(self, master_key_b64: str):
        raw = base64.b64decode(master_key_b64)
        if len(raw) != 32:
            raise ValueError("master key must be 32 bytes (base64-encoded)")
        self._aesgcm = AESGCM(raw)

    def encrypt(self, tenant_id: str, key_name: str, plaintext: str) -> dict:
        aad = f"{tenant_id}:{key_name}".encode()
        iv = os.urandom(12)
        ct = self._aesgcm.encrypt(iv, plaintext.encode(), aad)
        return {
            "encrypted_value": ct[:-16],
            "iv": iv,
            "auth_tag": ct[-16:],
        }

    def decrypt(self, tenant_id: str, key_name: str,
                encrypted_value: bytes, iv: bytes, auth_tag: bytes) -> str:
        aad = f"{tenant_id}:{key_name}".encode()
        plaintext = self._aesgcm.decrypt(iv, encrypted_value + auth_tag, aad)
        return plaintext.decode()
