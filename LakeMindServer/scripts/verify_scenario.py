#!/usr/bin/env python3
"""LakeMind 端到端真实场景验证。

场景：智能客服 Agent 知识库系统
  模拟一个客服 Agent 从启动到提供问答服务的完整流程，
  覆盖方案中全部五个数据域：

  1. 结构化数据域：Iceberg 表存 Agent 任务日志，DuckDB 即席查询
  2. 知识/文档 RAG 域：文档存 S3（Gravitino Fileset 管理），Lance 向量索引，LanceDB 检索
  3. 短期/工作记忆域：Dragonfly 存会话状态（TTL）
  4. 长期/语义记忆域：Lance 向量 + Iceberg 元信息小表（lance_uri 关联）
  5. Skills 域：技能文件存 S3，元信息存 Iceberg，LanceDB 语义检索

依赖：boto3 redis pyiceberg[pyarrow] pylance lancedb duckdb daft pyarrow
运行：python scripts/verify_scenario.py
"""
import os
import sys
import json
import time
import uuid
import shutil
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Windows 控制台 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 配置 ──────────────────────────────────────────────
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_AK = os.getenv("S3_ACCESS_KEY", "admin")
S3_SK = os.getenv("S3_SECRET_KEY", "admin123456")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

DRAGONFLY_HOST = os.getenv("DRAGONFLY_HOST", "localhost")
DRAGONFLY_PORT = int(os.getenv("DRAGONFLY_PORT", "6379"))

GRAVITINO_URI = os.getenv("GRAVITINO_URI", "http://localhost:8090")
METALAKE = os.getenv("GRAVITINO_METALAKE", "lakemind_metalake")

LANCE_DIR = Path(os.getenv("LANCE_DB_URI", "lance:///data/lance")
                  .replace("lance://", "")).resolve()
if not LANCE_DIR.exists():
    LANCE_DIR = Path("data/lance")
LANCE_DIR.mkdir(parents=True, exist_ok=True)

# 临时 SQL catalog for PyIceberg
CATALOG_DB = Path(tempfile.gettempdir()) / "lakemind_catalog.db"

passed = 0
failed = 0


def ok(name, detail=""):
    global passed
    passed += 1
    print(f"  [PASS] {name} {detail}")


def fail(name, detail=""):
    global failed
    failed += 1
    print(f"  [FAIL] {name} {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def s3_client():
    import boto3
    from botocore.client import Config
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_AK,
        aws_secret_access_key=S3_SK, region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


# ── 1. 结构化数据域 ────────────────────────────────────
def test_structured_data():
    section("1. 结构化数据域：Iceberg + S3 + DuckDB")
    try:
        import pyarrow as pa
        from pyiceberg.catalog import load_catalog
        from pyiceberg.schema import Schema
        from pyiceberg.types import (
            NestedField, StringType, TimestamptzType, LongType
        )

        s3 = s3_client()
        bucket = "lakemind-iceberg"
        try:
            s3.create_bucket(Bucket=bucket)
        except Exception:
            pass

        # 清理旧 catalog
        if CATALOG_DB.exists():
            CATALOG_DB.unlink()

        catalog = load_catalog(
            "lakemind",
            **{
                "type": "sql",
                "uri": f"sqlite:///{CATALOG_DB}",
                "warehouse": f"s3://{bucket}/warehouse",
                "s3.endpoint": S3_ENDPOINT,
                "s3.access-key-id": S3_AK,
                "s3.secret-access-key": S3_SK,
                "s3.region": S3_REGION,
            },
        )

        namespace = "agent_logs"
        try:
            catalog.create_namespace(namespace)
        except Exception:
            pass

        schema = Schema(
            NestedField(1, "log_id", StringType()),
            NestedField(2, "agent_id", StringType()),
            NestedField(3, "task_type", StringType()),
            NestedField(4, "status", StringType()),
            NestedField(5, "duration_ms", LongType()),
            NestedField(6, "created_at", TimestamptzType()),
        )

        table_name = f"{namespace}.task_logs"
        try:
            catalog.drop_table(table_name)
        except Exception:
            pass

        table = catalog.create_table(
            table_name,
            schema=schema,
            location=f"s3://{bucket}/warehouse/agent_logs/task_logs",
        )
        ok("创建 Iceberg 表", f"(schema: {len(schema.fields)} fields)")

        # 写入数据
        now = datetime.now(timezone.utc)
        records = pa.table({
            "log_id": [f"log-{i:03d}" for i in range(1, 21)],
            "agent_id": ["agent-cs-01"] * 10 + ["agent-cs-02"] * 10,
            "task_type": ["qa"] * 8 + ["search"] * 4 + ["qa"] * 5 + ["summarize"] * 3,
            "status": ["success"] * 15 + ["failed"] * 3 + ["success"] * 2,
            "duration_ms": [120, 85, 200, 95, 150, 110, 300, 88,
                            450, 500, 420, 380,
                            130, 90, 175, 100, 105,
                            600, 550, 140],
            "created_at": [now] * 20,
        })
        table.append(records)
        ok("写入 20 条任务日志", f"({records.num_rows} rows)")

        # 读取验证
        reader = table.scan().to_arrow()
        assert reader.num_rows == 20, f"expected 20, got {reader.num_rows}"
        ok("读取 Iceberg 表", f"({reader.num_rows} rows)")

        # DuckDB 即席查询
        import duckdb
        con = duckdb.connect()
        df = reader.to_pandas()
        con.register("task_logs", df)

        total = con.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0]
        assert total == 20
        ok("DuckDB COUNT(*)", f"({total} rows)")

        by_agent = con.execute("""
            SELECT agent_id, COUNT(*) as cnt, AVG(duration_ms) as avg_ms
            FROM task_logs GROUP BY agent_id ORDER BY agent_id
        """).fetchall()
        ok("DuckDB 聚合查询", f"(agents: {len(by_agent)})")

        fail_rate = con.execute("""
            SELECT task_type,
                   ROUND(SUM(CASE WHEN status='failed' THEN 1.0 ELSE 0 END)
                         / COUNT(*), 2) as fail_rate
            FROM task_logs GROUP BY task_type ORDER BY fail_rate DESC
        """).fetchall()
        ok("DuckDB 失败率分析", f"({fail_rate})")

        con.close()
    except Exception as e:
        import traceback
        fail("结构化数据域", traceback.format_exc().split("\n")[-2])


# ── 2. 知识/文档 RAG 域 ────────────────────────────────
def test_knowledge_rag():
    section("2. 知识/文档 RAG 域：S3 + Lance + LanceDB")
    try:
        import pyarrow as pa
        import lance
        import lancedb

        s3 = s3_client()
        bucket = "lakemind-filesets"

        # 上传知识文档到 S3
        docs = {
            "knowledge/docs/faq-return-policy.md": "# 退货政策\n\n7天内可退货，需保留原包装。",
            "knowledge/docs/faq-shipping.md": "# 配送说明\n\n全国包邮，3-5个工作日送达。",
            "knowledge/docs/faq-payment.md": "# 支付方式\n\n支持微信、支付宝、银行卡支付。",
            "knowledge/docs/product-spec.md": "# 产品规格\n\n尺寸: 30x20x15cm, 重量: 1.2kg, 材质: ABS。",
        }
        for key, text in docs.items():
            s3.put_object(Bucket=bucket, Key=key, Body=text.encode("utf-8"))
        ok(f"上传 {len(docs)} 篇知识文档到 S3", f"(bucket: {bucket})")

        # 构造文档向量（模拟 embedding，用确定性向量代替）
        import hashlib
        import struct

        def mock_embedding(text: str, dim: int = 128) -> list:
            h = hashlib.sha256(text.encode()).digest()
            vec = []
            for i in range(dim):
                b = h[(i * 4) % len(h):(i * 4) % len(h) + 4]
                if len(b) < 4:
                    b = b + h[:4 - len(b)]
                val = struct.unpack("f", b)[0]
                vec.append(val)
            norm = sum(x * x for x in vec) ** 0.5
            return [x / norm for x in vec] if norm > 0 else vec

        # 创建 Lance 向量数据集
        records = []
        for key, text in docs.items():
            records.append({
                "doc_uri": f"s3://{bucket}/{key}",
                "title": key.split("/")[-1],
                "content": text[:100],
                "vector": mock_embedding(text),
            })

        arrow_table = pa.table({
            "doc_uri": [r["doc_uri"] for r in records],
            "title": [r["title"] for r in records],
            "content": [r["content"] for r in records],
            "vector": pa.array([r["vector"] for r in records],
                               type=pa.list_(pa.float32(), 128)),
        })

        lance_path = str(LANCE_DIR / "knowledge_vectors")
        if Path(lance_path).exists():
            shutil.rmtree(lance_path)

        db = lancedb.connect(str(LANCE_DIR))
        try:
            db.drop_table("knowledge_vectors")
        except Exception:
            pass
        table = db.create_table("knowledge_vectors", data=arrow_table, mode="overwrite")
        ok("创建 Lance 向量数据集", f"({table.count_rows()} docs, 128-dim)")

        # LanceDB 向量检索
        query_text = "退货流程是什么"
        query_vec = mock_embedding(query_text)
        results = table.search(query_vec).limit(2).to_list()
        ok("LanceDB 向量检索", f"(query='{query_text}', top2: {[r['title'] for r in results]})")

        # 验证结果合理性
        assert len(results) == 2
        assert "doc_uri" in results[0]
        ok("检索结果含 doc_uri", f"({results[0]['doc_uri'][:40]}...)")

        # 从 S3 拉回原文（RAG 完整流程）
        top_uri = results[0]["doc_uri"]
        s3_key = top_uri.replace(f"s3://{bucket}/", "")
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        content = obj["Body"].read().decode("utf-8")
        ok("RAG 完整流程：检索→S3取原文", f"(content: {content[:30]}...)")

    except Exception as e:
        import traceback
        fail("知识/文档 RAG 域", traceback.format_exc().split("\n")[-2])


# ── 3. 短期/工作记忆域 ─────────────────────────────────
def test_short_memory():
    section("3. 短期/工作记忆域：Dragonfly (TTL KV)")
    try:
        import redis
        r = redis.Redis(host=DRAGONFLY_HOST, port=DRAGONFLY_PORT,
                        socket_timeout=5, decode_responses=True)

        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        agent_id = "agent-cs-01"

        # 写入会话状态
        session = {
            "agent_id": agent_id,
            "status": "active",
            "current_topic": "退货咨询",
            "turn_count": 1,
        }
        r.set(f"session:{session_id}", json.dumps(session), ex=3600)
        ok("写入会话状态", f"(session: {session_id[:12]}..., TTL=3600s)")

        # 读取
        data = r.get(f"session:{session_id}")
        assert data is not None
        loaded = json.loads(data)
        assert loaded["current_topic"] == "退货咨询"
        ok("读取会话状态", f"(topic: {loaded['current_topic']})")

        # 更新（模拟多轮对话）
        loaded["turn_count"] = 3
        loaded["current_topic"] = "退货流程详解"
        r.set(f"session:{session_id}", json.dumps(loaded), ex=3600)
        ttl = r.ttl(f"session:{session_id}")
        assert 3500 < ttl <= 3600
        ok("更新会话（多轮对话）", f"(turn: {loaded['turn_count']}, TTL: {ttl}s)")

        # 工作记忆：临时任务锁
        lock_key = f"lock:task:doc-index"
        assert r.set(lock_key, "processing", ex=300, nx=True)
        ok("任务锁（NX 互斥）", f"(key: {lock_key})")

        # 重复加锁失败
        assert not r.set(lock_key, "other", ex=300, nx=True)
        ok("重复加锁被拒", "(NX 语义正确)")

        # 释放锁
        r.delete(lock_key)
        assert r.set(lock_key, "processing", ex=300, nx=True)
        ok("释放后重新加锁", "(锁可复用)")

        # 短期缓存
        r.setex("cache:faq:return", 600, "7天可退货")
        assert r.get("cache:faq:return") == "7天可退货"
        ok("短期缓存", "(TTL=600s)")

        # 清理
        r.delete(f"session:{session_id}", lock_key, "cache:faq:return")

    except Exception as e:
        import traceback
        fail("短期记忆域", traceback.format_exc().split("\n")[-2])


# ── 4. 长期/语义记忆域 ─────────────────────────────────
def test_long_memory():
    section("4. 长期/语义记忆域：Lance 向量 + Iceberg 元信息小表")
    try:
        import pyarrow as pa
        import lance
        import lancedb
        from pyiceberg.catalog import load_catalog
        from pyiceberg.schema import Schema
        from pyiceberg.types import (
            NestedField, StringType, TimestampType, IntegerType
        )

        agent_id = "agent-cs-01"
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        # 4a. Lance 向量存储（长期记忆向量）
        import hashlib, struct

        def mock_embedding(text: str, dim: int = 64) -> list:
            h = hashlib.sha256(text.encode()).digest()
            vec = []
            for i in range(dim):
                b = h[(i * 4) % len(h):(i * 4) % len(h) + 4]
                if len(b) < 4:
                    b = b + h[:4 - len(b)]
                vec.append(struct.unpack("f", b)[0])
            norm = sum(x * x for x in vec) ** 0.5
            return [x / norm for x in vec] if norm > 0 else vec

        memories = [
            {"text": "用户询问了退货政策，我告知7天内可退", "ts": "2026-06-28T10:00:00Z"},
            {"text": "用户询问了配送时间，我告知3-5个工作日", "ts": "2026-06-29T14:00:00Z"},
            {"text": "用户询问了支付方式，我告知支持微信支付宝", "ts": "2026-06-30T09:00:00Z"},
        ]

        memory_records = []
        for i, m in enumerate(memories):
            mem_id = f"mem-{uuid.uuid4().hex[:8]}"
            lance_uri = str(LANCE_DIR / "memory_vectors" / f"{mem_id}.lance")
            memory_records.append({
                "memory_id": mem_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "content": m["text"],
                "vector": mock_embedding(m["text"], 64),
                "lance_uri": lance_uri,
                "created_at": m["ts"],
            })

        # 写入 Lance 向量
        arrow_vec = pa.table({
            "memory_id": [r["memory_id"] for r in memory_records],
            "content": [r["content"] for r in memory_records],
            "vector": pa.array([r["vector"] for r in memory_records],
                               type=pa.list_(pa.float32(), 64)),
        })

        lance_path = str(LANCE_DIR / "memory_vectors")
        if Path(lance_path).exists():
            shutil.rmtree(lance_path)
        db = lancedb.connect(str(LANCE_DIR))
        try:
            db.drop_table("memory_vectors")
        except Exception:
            pass
        mem_table = db.create_table("memory_vectors", data=arrow_vec, mode="overwrite")
        ok("写入长期记忆向量", f"({mem_table.count_rows()} memories, 64-dim)")

        # 4b. Iceberg 元信息小表（结构化元信息，lance_uri 关联）
        catalog = load_catalog(
            "lakemind",
            **{
                "type": "sql",
                "uri": f"sqlite:///{CATALOG_DB}",
                "warehouse": f"s3://lakemind-iceberg/warehouse",
                "s3.endpoint": S3_ENDPOINT,
                "s3.access-key-id": S3_AK,
                "s3.secret-access-key": S3_SK,
                "s3.region": S3_REGION,
            },
        )

        namespace = "agent_memory"
        try:
            catalog.create_namespace(namespace)
        except Exception:
            pass

        schema = Schema(
            NestedField(1, "memory_id", StringType()),
            NestedField(2, "agent_id", StringType()),
            NestedField(3, "session_id", StringType()),
            NestedField(4, "lance_uri", StringType()),
            NestedField(5, "created_at", StringType()),
        )

        table_name = f"{namespace}.memory_meta"
        try:
            catalog.drop_table(table_name)
        except Exception:
            pass

        meta_table = catalog.create_table(
            table_name,
            schema=schema,
            location=f"s3://lakemind-iceberg/warehouse/agent_memory/memory_meta",
        )

        meta_records = pa.table({
            "memory_id": [r["memory_id"] for r in memory_records],
            "agent_id": [r["agent_id"] for r in memory_records],
            "session_id": [r["session_id"] for r in memory_records],
            "lance_uri": [r["lance_uri"] for r in memory_records],
            "created_at": [r["created_at"] for r in memory_records],
        })
        meta_table.append(meta_records)
        ok("写入 Iceberg 元信息小表", f"({meta_records.num_rows} rows, lance_uri 关联)")

        # 4c. 查询：先从 Iceberg 查 agent 的记忆列表，再从 Lance 加载向量做检索
        import duckdb
        reader = meta_table.scan().to_arrow().to_pandas()
        con = duckdb.connect()
        con.register("memory_meta", reader)

        agent_memories = con.execute("""
            SELECT memory_id, lance_uri, created_at
            FROM memory_meta
            WHERE agent_id = ?
            ORDER BY created_at
        """, [agent_id]).fetchall()
        con.close()
        ok("Iceberg 查 agent 记忆列表", f"({len(agent_memories)} memories)")

        # 从 Lance 检索最相关记忆
        vec_table = db.open_table("memory_vectors")
        query_vec = mock_embedding("退货相关的问题", 64)
        results = vec_table.search(query_vec).limit(1).to_list()
        ok("LanceDB 语义检索长期记忆", f"(top1: {results[0]['content'][:25]}...)")

        # 验证双表关联
        assert len(agent_memories) == 3
        for mem in agent_memories:
            assert mem[1]  # lance_uri not null
        ok("双表 lance_uri 关联完整", "(3/3 memories have lance_uri)")

    except Exception as e:
        import traceback
        fail("长期记忆域", traceback.format_exc().split("\n")[-2])


# ── 5. Skills 域 ───────────────────────────────────────
def test_skills():
    section("5. Skills 域：SeaweedFS + Iceberg + LanceDB")
    try:
        import pyarrow as pa
        import lance
        import lancedb
        from pyiceberg.catalog import load_catalog
        from pyiceberg.schema import Schema
        from pyiceberg.types import (
            NestedField, StringType, IntegerType
        )
        import hashlib, struct

        def mock_embedding(text: str, dim: int = 64) -> list:
            h = hashlib.sha256(text.encode()).digest()
            vec = []
            for i in range(dim):
                b = h[(i * 4) % len(h):(i * 4) % len(h) + 4]
                if len(b) < 4:
                    b = b + h[:4 - len(b)]
                vec.append(struct.unpack("f", b)[0])
            norm = sum(x * x for x in vec) ** 0.5
            return [x / norm for x in vec] if norm > 0 else vec

        s3 = s3_client()
        bucket = "lakemind-filesets"

        # 5a. 技能文件存 S3
        skills = {
            "skills/document_qa.py": "def run(query): return f'QA: {query}'",
            "skills/doc_summarize.py": "def run(text): return text[:100]",
            "skills/data_export.py": "def run(table, fmt): return f'export {table}'",
        }
        for key, code_text in skills.items():
            s3.put_object(Bucket=bucket, Key=key, Body=code_text.encode("utf-8"))
        ok(f"上传 {len(skills)} 个技能文件到 S3", "(skills/)")

        # 5b. 技能元信息存 Iceberg
        catalog = load_catalog(
            "lakemind",
            **{
                "type": "sql",
                "uri": f"sqlite:///{CATALOG_DB}",
                "warehouse": f"s3://lakemind-iceberg/warehouse",
                "s3.endpoint": S3_ENDPOINT,
                "s3.access-key-id": S3_AK,
                "s3.secret-access-key": S3_SK,
                "s3.region": S3_REGION,
            },
        )

        namespace = "skills"
        try:
            catalog.create_namespace(namespace)
        except Exception:
            pass

        schema = Schema(
            NestedField(1, "skill_id", StringType()),
            NestedField(2, "name", StringType()),
            NestedField(3, "description", StringType()),
            NestedField(4, "version", StringType()),
            NestedField(5, "owner", StringType()),
            NestedField(6, "s3_uri", StringType()),
        )

        table_name = f"{namespace}.skill_meta"
        try:
            catalog.drop_table(table_name)
        except Exception:
            pass

        skill_table = catalog.create_table(
            table_name,
            schema=schema,
            location=f"s3://lakemind-iceberg/warehouse/skills/skill_meta",
        )

        skill_meta = [
            {"skill_id": "skill-001", "name": "document_qa", "description": "文档问答：根据知识库回答用户问题",
             "version": "1.0.0", "owner": "agent-cs-01", "s3_uri": f"s3://{bucket}/skills/document_qa.py"},
            {"skill_id": "skill-002", "name": "doc_summarize", "description": "文档摘要：提取文本关键信息生成摘要",
             "version": "1.0.0", "owner": "agent-cs-01", "s3_uri": f"s3://{bucket}/skills/doc_summarize.py"},
            {"skill_id": "skill-003", "name": "data_export", "description": "数据导出：将查询结果导出为CSV或Excel",
             "version": "1.2.0", "owner": "agent-cs-02", "s3_uri": f"s3://{bucket}/skills/data_export.py"},
        ]

        meta_arrow = pa.table({
            "skill_id": [r["skill_id"] for r in skill_meta],
            "name": [r["name"] for r in skill_meta],
            "description": [r["description"] for r in skill_meta],
            "version": [r["version"] for r in skill_meta],
            "owner": [r["owner"] for r in skill_meta],
            "s3_uri": [r["s3_uri"] for r in skill_meta],
        })
        skill_table.append(meta_arrow)
        ok("写入技能元信息到 Iceberg", f"({meta_arrow.num_rows} skills)")

        # 5c. Lance 向量索引支撑语义检索
        vec_records = pa.table({
            "skill_id": [r["skill_id"] for r in skill_meta],
            "name": [r["name"] for r in skill_meta],
            "description": [r["description"] for r in skill_meta],
            "vector": pa.array(
                [mock_embedding(r["description"], 64) for r in skill_meta],
                type=pa.list_(pa.float32(), 64)),
        })

        lance_path = str(LANCE_DIR / "skill_vectors")
        if Path(lance_path).exists():
            shutil.rmtree(lance_path)
        db = lancedb.connect(str(LANCE_DIR))
        try:
            db.drop_table("skill_vectors")
        except Exception:
            pass
        vec_table = db.create_table("skill_vectors", data=vec_records, mode="overwrite")
        ok("创建技能语义索引", f"({vec_table.count_rows()} skills, 64-dim)")

        # 5d. 语义检索："找一个能做文档问答的 Skill"
        query_vec = mock_embedding("我需要一个能回答文档问题的技能", 64)
        results = vec_table.search(query_vec).limit(1).to_list()
        best_skill = results[0]["name"]
        ok("语义检索 Skills", f"(query='文档问答' → best: {best_skill})")
        assert best_skill == "document_qa", f"expected document_qa, got {best_skill}"
        ok("检索结果正确", "(document_qa)")

        # 5e. 从 S3 拉取技能代码
        skill_uri = next(
            r["s3_uri"] for r in skill_meta if r["name"] == best_skill
        )
        s3_key = skill_uri.replace(f"s3://{bucket}/", "")
        code = s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
        ok("从 S3 加载技能代码", f"({len(code)} bytes)")

    except Exception as e:
        import traceback
        fail("Skills 域", traceback.format_exc().split("\n")[-2])


# ── 主流程 ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  LakeMind 端到端真实场景验证")
    print("  场景：智能客服 Agent 知识库系统")
    print("=" * 60)
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  S3：{S3_ENDPOINT}")
    print(f"  Dragonfly：{DRAGONFLY_HOST}:{DRAGONFLY_PORT}")
    print(f"  Gravitino：{GRAVITINO_URI}")
    print(f"  Lance 目录：{LANCE_DIR}")

    test_structured_data()
    test_knowledge_rag()
    test_short_memory()
    test_long_memory()
    test_skills()

    print(f"\n{'='*60}")
    print(f"  结果：{passed} 通过, {failed} 失败")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
