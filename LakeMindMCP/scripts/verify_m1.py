"""M1 集成验证：业务 Agent 经 MCP 读写结构化数据（Data 资产）。

前置：LakeMindServer 已启动（S3/Gravitino/Dragonfly）。
运行：python scripts/verify_m1.py
"""
import sys, asyncio, threading, time, json
sys.path.insert(0, "src")

import uvicorn
from lakemindmcp.config import load_config
from lakemindmcp.server import build_app
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp_client_helpers import tool_json, res_json

cfg = load_config("config/config.local.yaml")
app = build_app(cfg)


def _clean_s3():
    """清理 retail 租户在 S3 warehouse 的残留数据，保证可重复运行。"""
    import boto3
    from botocore.client import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=cfg.engines.s3.endpoint,
        aws_access_key_id=cfg.engines.s3.access_key,
        aws_secret_access_key=cfg.engines.s3.secret_key,
        region_name=cfg.engines.s3.region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    for bucket in ("lakemind-iceberg", "lakemind-filesets"):
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception:
            continue
        paginator = s3.get_paginator("list_objects_v2")
        for prefix in ("warehouse/retail/", "retail/"):
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if objs:
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})


_clean_s3()
import os
from pathlib import Path
_cat_path = Path(cfg.engines.iceberg.sql_uri.split("sqlite:///", 1)[-1]).resolve()
if _cat_path.exists():
    _cat_path.unlink()

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8402, log_level="warning"))
t = threading.Thread(target=server.run, daemon=True)
t.start()
time.sleep(1.5)

passed = failed = 0
def ok(n, d=""): 
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""): 
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")


async def run():
    good = cfg.tokens[0].token  # business, tenant=retail
    base = "http://127.0.0.1:8402/mcp"
    async with streamablehttp_client(base, headers={"Authorization": f"Bearer {good}"}) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()

            # capabilities 资源
            caps = res_json(await sess.read_resource("lake://capabilities"))
            ok("read lake://capabilities", f"(types: {list(caps.keys())})")
            assert "data" in caps

            # workspace
            ws = res_json(await sess.read_resource("lake://workspace"))
            ok("read lake://workspace", f"(tenant: {ws['tenant_id']})")
            assert ws["tenant_id"] == "retail"

            # write_table
            rows = [
                {"log_id": f"l-{i}", "agent_id": "a1", "status": "success" if i % 3 else "failed", "duration_ms": 100 + i}
                for i in range(1, 11)
            ]
            wr = tool_json(await sess.call_tool("write_table", {"table": "task_logs", "rows": rows, "mode": "append"}))
            ok("write_table", f"({wr})")
            assert wr["rows_written"] == 10

            # query_table
            qr = tool_json(await sess.call_tool("query_table", {"table": "task_logs", "limit": 5}))
            ok("query_table", f"({qr['count']} rows)")
            assert qr["count"] == 5

            # query_table with filter
            fr = tool_json(await sess.call_tool("query_table", {"table": "task_logs", "filter": "status = 'failed'", "limit": 10}))
            ok("query_table filter", f"({fr['count']} failed)")
            assert fr["count"] > 0

            # execute_sql
            sr = tool_json(await sess.call_tool("execute_sql", {"sql": "SELECT status, COUNT(*) AS c FROM task_logs GROUP BY status ORDER BY status"}))
            ok("execute_sql", f"({sr['rows']})")
            assert len(sr["rows"]) == 2

            # lake://data 资源
            dlist = res_json(await sess.read_resource("lake://data"))
            ok("read lake://data", f"({[d.get('name') for d in dlist]})")
            assert any(d.get("name") == "task_logs" for d in dlist)

            # lake://data/{name} 资源
            desc = res_json(await sess.read_resource("lake://data/task_logs"))
            ok("read lake://data/task_logs", f"(rows: {desc.get('row_count')})")
            assert desc["row_count"] == 10

    # 租户隔离：steward (tenant=platform) 不应看到 retail 的表
    steward = cfg.tokens[1].token
    async with streamablehttp_client(base, headers={"Authorization": f"Bearer {steward}"}) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            dlist = res_json(await sess.read_resource("lake://data"))
            names = [d.get("name") for d in dlist]
            ok("tenant isolation: steward sees no retail tables", f"({names})")
            assert "task_logs" not in names

asyncio.run(run())
server.should_exit = True
print(f"\n[M1] {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
