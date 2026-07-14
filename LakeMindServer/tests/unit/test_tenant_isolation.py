from __future__ import annotations
from lakemind_server.security.tenant_isolation import (
    resolve_s3_key, resolve_s3_bucket, resolve_lance_uri,
    resolve_iceberg_namespace, resolve_valkey_key
)


class TestTenantIsolation:
    def test_s3_key_has_tenant_prefix(self):
        key = resolve_s3_key("ten_a", "ast_1", "bnd_1", "file.txt")
        assert key.startswith("ten_a/ast_1/")

    def test_s3_bucket_has_tenant(self):
        bucket = resolve_s3_bucket("ten_a")
        assert "ten_a" in bucket

    def test_lance_uri_has_tenant(self):
        uri = resolve_lance_uri("ten_a", "ast_1")
        assert uri.startswith("ten_a/")

    def test_iceberg_namespace_has_tenant(self):
        ns = resolve_iceberg_namespace("ten_a", "knowledge")
        assert ns.startswith("ten_a.")

    def test_valkey_key_has_tenant(self):
        key = resolve_valkey_key("ten_a", "session_1")
        assert key.startswith("ten_a:")

    def test_different_tenants_different_paths(self):
        a = resolve_s3_key("ten_a", "ast_1", "bnd_1", "f.txt")
        b = resolve_s3_key("ten_b", "ast_1", "bnd_1", "f.txt")
        assert a != b
