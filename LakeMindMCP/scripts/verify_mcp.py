"""LakeMindMCP 端到端集成验证。

前置：LakeMindServer 已启动（S3/Gravitino/Dragonfly）。
本脚本会自动启动一个 mock embedding 测试服务（OpenAI 兼容）。
运行：python scripts/verify_mcp.py
"""
import sys, os, asyncio, threading, time, json, uuid
from pathlib import Path
sys.path.insert(0, "src")

import uvicorn
from lakemindmcp.config import load_config
from lakemindmcp.server import build_app
from lakemindmcp.engines import build_engines
from lakemindmcp.context import TenantContext
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp_client_helpers import tool_json, res_json

# ── 启动 mock embedding 服务 ─────────────────────────────
import importlib.util
spec = importlib.util.spec_from_file_location("mock_emb", "scripts/mock_embedding_server.py")
mock_emb = importlib.util.module_from_spec(spec); spec.loader.exec_module(mock_emb)
emb_server = uvicorn.Server(uvicorn.Config(mock_emb.build_app(), host="127.0.0.1", port=8081, log_level="warning"))
threading.Thread(target=emb_server.run, daemon=True).start()

cfg = load_config("config/config.local.yaml")


# ── 清理残留 ─────────────────────────────────────────────
def _clean():
    import boto3
    from botocore.client import Config
    s3 = boto3.client("s3", endpoint_url=cfg.engines.s3.endpoint,
                      aws_access_key_id=cfg.engines.s3.access_key,
                      aws_secret_access_key=cfg.engines.s3.secret_key,
                      region_name=cfg.engines.s3.region,
                      config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
    for bucket in ("lakemind-iceberg", "lakemind-filesets"):
        try: s3.head_bucket(Bucket=bucket)
        except Exception: continue
        pg = s3.get_paginator("list_objects_v2")
        for pre in ("warehouse/retail/", "warehouse/platform/", "retail/", "platform/"):
            for p in pg.paginate(Bucket=bucket, Prefix=pre):
                objs = [{"Key": o["Key"]} for o in p.get("Contents", [])]
                if objs: s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})
    cat = Path(cfg.engines.iceberg.sql_uri.split("sqlite:///", 1)[-1]).resolve()
    if cat.exists(): cat.unlink()
    # 清理 Lance 租户目录
    lance_root = Path(cfg.engines.lance.uri).resolve()
    for d in ("tenant_retail", "tenant_platform"):
        p = lance_root / d
        if p.exists():
            import shutil; shutil.rmtree(p, ignore_errors=True)


_clean()
app = build_app(cfg)
mcp_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8405, log_level="warning"))
threading.Thread(target=mcp_server.run, daemon=True).start()
time.sleep(2.0)

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")

BASE = "http://127.0.0.1:8405/mcp"
BIZ = cfg.tokens[0].token      # business, retail, [data]
STEWARD = cfg.tokens[1].token  # steward, platform, [admin,data]


def client(token):
    return streamablehttp_client(BASE, headers={"Authorization": f"Bearer {token}"})


async def run():
    # ── 1. 认证 ──────────────────────────────────────────
    try:
        async with client("wrong-token") as (r, w, _):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
        fail("bad token rejected")
    except Exception:
        ok("bad token rejected at connect")

    # ── 2. 业务 Agent 全流程 ────────────────────────────
    async with client(BIZ) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()

            # capabilities
            caps = res_json(await sess.read_resource("lake://capabilities"))
            ok("capabilities", f"(types: {list(caps.keys())})")
            assert set(caps.keys()) == {"data", "knowledge", "memory", "skill", "experience", "ontology"}
            assert caps["ontology"]["enabled"] is False

            # ontology 占位
            ont = res_json(await sess.read_resource("lake://ontology"))
            ok("ontology disabled", f"({ont['status']})")
            assert ont["status"] == "disabled"

            # ── Data ─────────────────────────────────────
            rows = [{"log_id": f"l-{i}", "status": "success" if i % 3 else "failed", "duration_ms": 100 + i} for i in range(1, 11)]
            wr = tool_json(await sess.call_tool("write_table", {"table": "task_logs", "rows": rows}))
            ok("data write_table", f"({wr['rows_written']} rows)")
            qr = tool_json(await sess.call_tool("query_table", {"table": "task_logs", "limit": 5}))
            ok("data query_table", f"({qr['count']} rows)")
            sr = tool_json(await sess.call_tool("execute_sql", {"sql": "SELECT status, COUNT(*) AS c FROM task_logs GROUP BY status"}))
            ok("data execute_sql", f"({len(sr['rows'])} groups)")
            assert len(sr["rows"]) == 2

            # ── Memory ───────────────────────────────────
            mem1 = tool_json(await sess.call_tool("remember", {"content": "用户询问了退货政策，我告知7天内可退", "context": {"session_id": "s1"}, "ttl": 3600}))
            ok("memory remember", f"({mem1['memory_id'][:12]}...)")
            mem2 = tool_json(await sess.call_tool("remember", {"content": "用户询问了配送时间，我告知3-5个工作日"}))
            ok("memory remember 2", "")
            rc = tool_json(await sess.call_tool("recall", {"query": "退货", "limit": 1}))
            ok("memory recall", f"({rc['count']} match, top: {rc['memories'][0]['content'][:15]}...)")
            assert rc["count"] == 1
            ov = res_json(await sess.read_resource("lake://memory"))
            ok("memory overview", f"(long: {ov['long_term_count']})")
            assert ov["long_term_count"] == 2
            fg = tool_json(await sess.call_tool("forget", {"query": "退货"}))
            ok("memory forget", f"(deleted: {fg['deleted']})")
            assert fg["deleted"] >= 1

            # ── Experience ───────────────────────────────
            exp = tool_json(await sess.call_tool("record_experience", {"type": "success", "content": "成功处理退货咨询", "tags": ["refund", "cs"]}))
            ok("experience record", f"({exp['exp_id'][:12]}...)")
            exp_list = res_json(await sess.read_resource("lake://experience"))
            ok("experience list", f"({len(exp_list)} records)")
            assert len(exp_list) == 1

            # ── 跨 scope：业务 Agent 调 admin 工具应被拒 ──
            res = await sess.call_tool("get_system_health", {})
            if res.isError:
                ok("business agent blocked from admin tool")
            else:
                fail("business agent blocked from admin", "admin tool callable by data-scope agent")

    # ── 3. Steward admin 流程 ───────────────────────────
    async with client(STEWARD) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()

            # system health
            h = tool_json(await sess.call_tool("get_system_health", {}))
            ok("admin get_system_health", f"({h})")
            assert h["s3"] == "ok" and h["dragonfly"] == "ok"

            # create_dataset
            ds = tool_json(await sess.call_tool("create_dataset", {"name": "metrics", "schema": {"ts": "timestamp", "value": "float64"}}))
            ok("admin create_dataset", f"({ds['dataset']})")

            # register_skill
            sk = tool_json(await sess.call_tool("register_skill", {"name": "doc_qa", "location": "s3://lakemind-filesets/skills", "metadata": {"description": "文档问答：根据知识库回答用户问题", "version": "1.0.0", "code": "def run(q): return f'QA: {q}'"}}))
            ok("admin register_skill", f"({sk['skill_id'][:12]}...)")
            sk2 = tool_json(await sess.call_tool("register_skill", {"name": "data_export", "location": "s3://lakemind-filesets/skills", "metadata": {"description": "数据导出：将查询结果导出为CSV", "code": "def run(t): return f'export {t}'"}}))
            ok("admin register_skill 2", "")

            # search_skill
            ss = tool_json(await sess.call_tool("search_skill", {"query": "我需要一个能回答文档问题的技能"}))
            ok("skill search", f"(top: {ss['skills'][0]['name']})")
            assert ss["skills"][0]["name"] == "doc_qa"

            # read skill resource (含代码)
            sk_desc = res_json(await sess.read_resource(f"lake://skills/{sk['skill_id']}"))
            ok("skill resource read", f"(code loaded: {len(sk_desc['code'])} bytes)")
            assert "def run" in sk_desc["code"]

    # ── 4. Knowledge（steward 注册 + 业务 Agent 检索）────
    # 用 steward 注册知识库，直接灌入文档向量（MVP 无 ingest 工具，走引擎）
    eng = build_engines(cfg)
    pctx = TenantContext("platform", "steward")
    import pyarrow as pa
    kb_table = "kb_faq"
    docs = [
        ("faq-return", "退货政策：7天内可退货，需保留原包装。"),
        ("faq-shipping", "配送说明：全国包邮，3-5个工作日送达。"),
        ("faq-payment", "支付方式：支持微信、支付宝、银行卡支付。"),
    ]
    dim = eng.embedding.dim
    vecs = eng.embedding.embed([d[1] for d in docs])
    rows = pa.table({
        "doc_uri": [f"s3://lakemind-filesets/platform/knowledge/{d[0]}.md" for d in docs],
        "title": [d[0] for d in docs],
        "content": [d[1] for d in docs],
        "vector": pa.array(vecs, type=pa.list_(pa.float32(), dim)),
    })
    eng.lancedb.create_table(pctx, kb_table, rows, mode="overwrite")

    async with client(STEWARD) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            klist = res_json(await sess.read_resource("lake://knowledge"))
            ok("knowledge list", f"({[k.get('name') for k in klist]})")
            assert any(k.get("name") == "kb_faq" for k in klist)
            ks = tool_json(await sess.call_tool("search_knowledge", {"fileset": "faq", "query": "退货流程", "top_k": 2}))
            ok("knowledge search", f"(top: {ks['hits'][0]['title']})")
            assert ks["count"] == 2
            assert ks["hits"][0]["title"] == "faq-return"

    # ── 5. 租户隔离 ─────────────────────────────────────
    async with client(BIZ) as (r, w, _):
        async with ClientSession(r, w) as sess:
            await sess.initialize()
            # retail Agent 看不到 platform 的知识库
            klist = res_json(await sess.read_resource("lake://knowledge"))
            ok("tenant isolation: knowledge", f"({[k.get('name') for k in klist]})")
            assert not any(k.get("name") == "kb_faq" for k in klist)
            # retail Agent 看不到 platform 的 skills
            slist = res_json(await sess.read_resource("lake://skills"))
            ok("tenant isolation: skills", f"({len(slist)} skills)")
            assert all(s.get("name") not in ("doc_qa", "data_export") for s in slist)

asyncio.run(run())
emb_server.should_exit = True
mcp_server.should_exit = True
print(f"\n[verify_mcp] {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
