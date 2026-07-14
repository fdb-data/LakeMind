from __future__ import annotations
import os
import base64
import pytest
from lakemind_server.security.crypto import encrypt, decrypt


@pytest.fixture(autouse=True)
def _set_master_key():
    key = base64.b64encode(os.urandom(32)).decode()
    old = os.environ.get("LAKEMIND_MASTER_KEY")
    os.environ["LAKEMIND_MASTER_KEY"] = key
    yield
    if old:
        os.environ["LAKEMIND_MASTER_KEY"] = old
    else:
        del os.environ["LAKEMIND_MASTER_KEY"]


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "hello world"
        ct = encrypt(plaintext)
        assert decrypt(ct) == plaintext

    def test_encrypt_different_each_time(self):
        pt = "same text"
        ct1 = encrypt(pt)
        ct2 = encrypt(pt)
        assert ct1 != ct2

    def test_decrypt_with_aad(self):
        plaintext = "secret data"
        aad = b"tenant_a"
        ct = encrypt(plaintext, aad=aad)
        assert decrypt(ct, aad=aad) == plaintext

    def test_decrypt_wrong_aad_fails(self):
        plaintext = "secret data"
        ct = encrypt(plaintext, aad=b"tenant_a")
        with pytest.raises(Exception):
            decrypt(ct, aad=b"tenant_b")

    def test_encrypt_empty_string(self):
        ct = encrypt("")
        assert decrypt(ct) == ""

    def test_encrypt_unicode(self):
        plaintext = "你好世界 🌍"
        ct = encrypt(plaintext)
        assert decrypt(ct) == plaintext
