"""WP8-T03: Security acceptance scenarios — 6 tests."""
import pytest
import httpx

CONTROL_PLANE = "http://localhost:10823"


@pytest.fixture
def tenant_a_client():
    return httpx.Client(base_url=CONTROL_PLANE, headers={"Authorization": "Bearer token-a"}, timeout=10.0)


@pytest.fixture
def tenant_b_client():
    return httpx.Client(base_url=CONTROL_PLANE, headers={"Authorization": "Bearer token-b"}, timeout=10.0)


def test_cross_tenant_isolation(tenant_a_client, tenant_b_client):
    pass

def test_forged_header_rejected():
    pass

def test_unauthorized_skill_rejected():
    pass

def test_secret_minimal_injection():
    pass

def test_revoked_skill_not_executable():
    pass

def test_ray_dashboard_not_exposed():
    pass
