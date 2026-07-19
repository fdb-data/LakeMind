from lakemind_server.services.search_service import SearchService
from lakemind_server.db import execute

tenants = execute("SELECT tenant_id, name, status FROM tenants")
for t in tenants:
    SearchService.upsert_projection(
        object_type="tenant", object_id=t["tenant_id"],
        title=t["name"], scope_type="PLATFORM", scope_id=None,
        subtitle="status=" + str(t["status"]), keywords="tenant",
    )

assets = execute("SELECT asset_id, name, asset_type, tenant_id FROM assets LIMIT 20")
for a in assets:
    SearchService.upsert_projection(
        object_type="asset", object_id=a["asset_id"],
        title=a.get("name") or a["asset_id"], scope_type="TENANT", scope_id=a.get("tenant_id"),
        subtitle="type=" + str(a.get("asset_type", "")), keywords="asset",
    )

jobs = execute("SELECT job_id, status, tenant_id FROM job_runs LIMIT 20")
for j in jobs:
    SearchService.upsert_projection(
        object_type="job", object_id=j["job_id"],
        title=j["job_id"], scope_type="TENANT", scope_id=j.get("tenant_id"),
        subtitle="status=" + str(j["status"]), keywords="job",
    )

print("Projections populated: tenants=%d, assets=%d, jobs=%d" % (len(tenants), len(assets), len(jobs)))
