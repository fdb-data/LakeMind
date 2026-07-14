from __future__ import annotations
import pytest
from lakemind_server.security.context import SecurityContext


def _ctx(roles=None, scopes=None, tenant="ten_a"):
    return SecurityContext(
        principal_id="prn_test",
        principal_type="agent",
        tenant_id=tenant,
        roles=roles or ["agent"],
        scopes=scopes or ["asset:read"],
        token_id="tok_test",
        request_id="req_test",
    )


class TestSecurityContext:
    def test_has_scope_true(self):
        ctx = _ctx(scopes=["asset:read"])
        assert ctx.has_scope("asset:read")

    def test_has_scope_false(self):
        ctx = _ctx(scopes=["asset:read"])
        assert not ctx.has_scope("asset:delete")

    def test_platform_admin_has_all_scopes(self):
        ctx = _ctx(roles=["platform_admin"], scopes=[])
        assert ctx.has_scope("asset:delete")
        assert ctx.has_scope("config:write")

    def test_can_access_own_tenant(self):
        ctx = _ctx(tenant="ten_a")
        assert ctx.can_access_tenant("ten_a")

    def test_cannot_access_other_tenant(self):
        ctx = _ctx(tenant="ten_a")
        assert not ctx.can_access_tenant("ten_b")

    def test_platform_admin_can_access_any_tenant(self):
        ctx = _ctx(roles=["platform_admin"], tenant="ten_a")
        assert ctx.can_access_tenant("ten_b")

    def test_is_platform_admin(self):
        ctx = _ctx(roles=["platform_admin"])
        assert ctx.is_platform_admin

    def test_is_tenant_admin(self):
        ctx = _ctx(roles=["tenant_admin"])
        assert ctx.is_tenant_admin
        assert not ctx.is_platform_admin
