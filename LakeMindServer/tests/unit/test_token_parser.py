from __future__ import annotations
import hashlib
from lakemind_server.security.token_parser import _hash_token


class TestTokenHash:
    def test_hash_is_sha256(self):
        token = "my-secret-token"
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert _hash_token(token) == expected

    def test_hash_is_deterministic(self):
        token = "same-token"
        assert _hash_token(token) == _hash_token(token)

    def test_hash_different_tokens(self):
        assert _hash_token("token-a") != _hash_token("token-b")

    def test_hash_returns_hex_string(self):
        h = _hash_token("test")
        assert len(h) == 64
        int(h, 16)
