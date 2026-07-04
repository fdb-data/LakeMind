"""容器化对接验证：连接已运行的容器化 LakeMindMCP (localhost:8400)。

前置：
  - LakeMindServer 容器在跑
  - LakeMindMCP 容器在跑 (docker compose up -d)
  - mock embedding 服务在宿主机 :8081 在跑（容器经 host.docker.internal 访问）
运行：python scripts/verify_docker.py
"""
import sys, os, asyncio, json, shutil
from pathlib import Path
sys.path.insert(0, "src")

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp_client_helpers import tool_json, res_json

BASE = "http://localhost:8400/mcp"
BIZ = "test-business-token"      # retail, [data]
STEWARD = "test-steward-token"   # platform, [admin,data]

# ── 清理残留（经宿主机 localhost:8333）──────────────────
import boto3
from botocore.client import Config
s3 = boto3.client("s3", endpoint_url="http://localhost:8333",
                  aws_access_key_id="admin", aws_secret_access_key="admin123456",
                  region_name="us-east-1",
                  config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
for bucket in ("lakemind-iceberg", "lakemind-filesets"):
    try: s3.head_bucket(Bucket=bucket)
    except Exception: continue
    pg = s3.get_paginator("list_objects_v2")
    for pre in ("warehouse/retail/", "warehouse/platform/", "retail/", "platform/"):
        for p in pg.paginate(Bucket=bucket, Prefix=pre):
            objs = [{"Key": o["Key"]} for o in p.get("Contents", [])]
            if objs: s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})
# 清理 Lance 租户目录（宿主机路径）
lance_root = Path("../LakeMindServer/data/lance").resolve()
for d in ("tenant_retail", "tenant_platform"):
    p = lance_root / d
    if p.exists(): shutil.rmtree(p, ignore_errors=True)

# 容器内 catalog db 在命名卷里，重建容器时已 fresh；如非 fresh 可重启
# 这里通过 docker 重置 catalog 卷
import subprocess
subprocess.run(["docker", "compose", "restart"], check=True, capture_output=True)
import time; time.sleep(4)

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")

def client(token):
    return streamablehttp_client(BASE, headers={"Authorization": f"Bearer {token}"})


async def run():
    # 1. 认证
    try:
        async with client("wrong-token") as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
        fail("bad token rejected")
    except Exception:
        ok("bad token rejected at connect")

    # 2. 业务 Agent
    async with client(BIZ) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            caps = res_json(await sess.read_resource("lake://capabilities"))
            ok("capabilities", f"({list(caps.keys())})")
            assert set(caps.keys()) == {"data", "knowledge", "memory", "skill", "experience", "ontology"}
            assert caps["ontology"]["enabled"] is False
            ont = res_json(await sess.read_resource("lake://ontology"))
            ok("ontology disabled", f"({ont['status']})")

            rows = [{"log_id": f"l-{i}", "status": "success" if i % 3 else "failed", "duration_ms": 100 + i} for i in range(1, 11)]
            wr = tool_json(await sess.call_tool("write_table", {"table": "task_logs", "rows": rows}))
            ok("data write_table", f"({wr['rows_written']} rows)")
            qr = tool_json(await sess.call_tool("query_table", {"table": "task_logs", "limit": 5}))
            ok("data query_table", f"({qr['count']} rows)")
            sr = tool_json(await sess.call_tool("execute_sql", {"sql": "SELECT status, COUNT(*) AS c FROM task_logs GROUP BY status"}))
            ok("data execute_sql", f"({len(sr['rows'])} groups)")
            assert len(sr["rows"]) == 2

            mem1 = tool_json(await sess.call_tool("remember", {"content": "用户询问了退货政策，我告知7天内可退", "context": {"session_id": "s1"}, "ttl": 3600}))
            ok("memory remember", f"({mem1['memory_id'][:12]}...)")
            tool_json(await sess.call_tool("remember", {"content": "用户询问了配送时间，我告知3-5个工作日"}))
            ok("memory remember 2", "")
            rc = tool_json(await sess.call_tool("recall", {"query": "退货", "limit": 1}))
            ok("memory recall", f"({rc['count']} match)")
            assert rc["count"] == 1
            ov = res_json(await sess.read_resource("lake://memory"))
            ok("memory overview", f"(long: {ov['long_term_count']})")
            assert ov["long_term_count"] == 2
            fg = tool_json(await sess.call_tool("forget", {"query": "退货"}))
            ok("memory forget", f"(deleted: {fg['deleted']})")
            assert fg["deleted"] >= 1

            exp = tool_json(await sess.call_tool("record_experience", {"type": "success", "content": "成功处理退货咨询", "tags": ["refund"]}))
            ok("experience record", f"({exp['exp_id'][:12]}...)")
            exp_list = res_json(await sess.read_resource("lake://experience"))
            ok("experience list", f"({len(exp_list)} records)")
            assert len(exp_list) == 1

            res = await sess.call_tool("get_system_health", {})
            if res.isError: ok("business agent blocked from admin tool")
            else: fail("business agent blocked from admin")

    # 3. Steward admin
    async with client(STEWARD) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            h = tool_json(await sess.call_tool("get_system_health", {}))
            ok("admin health", f"(s3={h['s3']} df={h['dragonfly']} gv={h['gravitino']} emb={h['embedding']})")
            assert h["s3"] == "ok" and h["dragonfly"] == "ok" and h["gravitino"] == "ok" and h["embedding"] == "ok"
            ds = tool_json(await sess.call_tool("create_dataset", {"name": "metrics", "schema": {"ts": "timestamp", "value": "float64"}}))
            ok("admin create_dataset", f"({ds['dataset']})")
            sk = tool_json(await sess.call_tool("register_skill", {"name": "doc_qa", "location": "s3://lakemind-filesets/skills", "metadata": {"description": "文档问答：根据知识库回答用户问题", "version": "1.0.0", "code": "def run(q): return f'QA: {q}'"}}))
            ok("admin register_skill", f"({sk['skill_id'][:12]}...)")
            tool_json(await sess.call_tool("register_skill", {"name": "data_export", "location": "s3://lakemind-filesets/skills", "metadata": {"description": "数据导出：将查询结果导出为CSV", "code": "def run(t): return f'export {t}'"}}))
            ok("admin register_skill 2", "")
            ss = tool_json(await sess.call_tool("search_skill", {"query": "我需要一个能回答文档问题的技能"}))
            ok("skill search", f"(top: {ss['skills'][0]['name']})")
            assert ss["skills"][0]["name"] == "doc_qa"
            sk_desc = res_json(await sess.read_resource(f"lake://skills/{sk['skill_id']}"))
            ok("skill resource read", f"(code: {len(sk_desc['code'])} bytes)")
            assert "def run" in sk_desc["code"]

    # 4. Knowledge（steward 灌数据 + 检索）
    sys.path.insert(0, "src")
    from lakemindmcp.config import load_config
    from lakemindmcp.engines import build_engines
    from lakemindmcp.context import TenantContext
    import pyarrow as pa
    dcfg = load_config("config/config.yaml")
    # 引擎用宿主机 localhost 连 Server
    dcfg.engines.s3.endpoint = "http://localhost:8333"
    dcfg.engines.gravitino.uri = "http://localhost:8090"
    dcfg.engines.dragonfly.host = "localhost"
    dcfg.engines.lance.uri = str(Path("../LakeMindServer/data/lance").resolve())
    dcfg.engines.iceberg.sql_uri = "sqlite:////tmp/lakemind-docker-verify-catalog.db"
    dcfg.embedding.base_url = "http://localhost:8081/v1"
    eng = build_engines(dcfg)
    pctx = TenantContext("platform", "steward")
    docs = [("faq-return", "退货政策：7天内可退货，需保留原包装。"), ("faq-shipping", "配送说明：全国包邮，3-5个工作日送达。"), ("faq-payment", "支付方式：支持微信、支付宝、银行卡支付。")]
    dim = eng.embedding.dim
    vecs = eng.embedding.embed([d[1] for d in docs])
    rows = pa.table({"doc_uri": [f"s3://lakemind-filesets/platform/knowledge/{d[0]}.md" for d in docs], "title": [d[0] for d in docs], "content": [d[1] for d in docs], "vector": pa.array(vecs, type=pa.list_(pa.float32(), dim))})
    eng.lancedb.create_table(pctx, "kb_faq", rows, mode="overwrite")

    async with client(STEWARD) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            klist = res_json(await sess.read_resource("lake://knowledge"))
            ok("knowledge list", f"({[k.get('name') for k in klist]})")
            assert any(k.get("name") == "kb_faq" for k in klist)
            ks = tool_json(await sess.call_tool("search_knowledge", {"fileset": "faq", "query": "退货流程", "top_k": 2}))
            ok("knowledge search", f"(top: {ks['hits'][0]['title']})")
            assert ks["count"] == 2 and ks["hits"][0]["title"] == "faq-return"

    # 5. 租户隔离
    async with client(BIZ) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            klist = res_json(await sess.read_resource("lake://knowledge"))
            ok("tenant iso: knowledge", f"({[k.get('name') for k in klist]})")
            assert not any(k.get("name") == "kb_faq" for k in klist)
            slist = res_json(await sess.read_resource("lake://skills"))
            ok("tenant iso: skills", f"({len(slist)} skills)")
            assert all(s.get("name") not in ("doc_qa", "data_export") for s in slist)

asyncio.run(run())
print(f"\n[verify_docker] {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
