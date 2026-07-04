#!/usr/bin/env python3
"""LakeMindServer 平台集成验证脚本。

端到端验证三大服务及 Gravitino->SeaweedFS S3 集成：
  1. SeaweedFS S3：建桶/上传/下载/列表/删除
  2. Dragonfly：set/get/TTL
  3. Gravitino REST：metalake + fileset 编目 -> S3 实际写入

依赖：boto3, redis   (pip install boto3 redis)
运行：python scripts/verify_services.py
"""
import os
import sys
import json
import time
import socket
import urllib.request
import urllib.error

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_AK = os.getenv("S3_ACCESS_KEY", "admin")
S3_SK = os.getenv("S3_SECRET_KEY", "admin123456")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

DRAGONFLY_HOST = os.getenv("DRAGONFLY_HOST", "localhost")
DRAGONFLY_PORT = int(os.getenv("DRAGONFLY_PORT", "6379"))

GRAVITINO_URI = os.getenv("GRAVITINO_URI", "http://localhost:8090")
METALAKE = os.getenv("GRAVITINO_METALAKE", "lakemind_metalake")

passed = 0
failed = 0


def ok(name, detail=""):
    global passed
    passed += 1
    print(f"[PASS] {name} {detail}")


def fail(name, detail=""):
    global failed
    failed += 1
    print(f"[FAIL] {name} {detail}")


# ---------- 1. SeaweedFS S3 ----------
def test_s3():
    import boto3
    from botocore.client import Config
    s3 = boto3.client(
        "s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_AK,
        aws_secret_access_key=S3_SK, region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    b = "lakemind-smoke"
    try:
        s3.create_bucket(Bucket=b)
        s3.put_object(Bucket=b, Key="hello.txt", Body=b"hello lakemind")
        body = s3.get_object(Bucket=b, Key="hello.txt")["Body"].read()
        assert body == b"hello lakemind", body
        keys = [o["Key"] for o in s3.list_objects_v2(Bucket=b).get("Contents", [])]
        assert "hello.txt" in keys
        s3.delete_object(Bucket=b, Key="hello.txt")
        s3.delete_bucket(Bucket=b)
        ok("SeaweedFS S3 CRUD", "(put/get/list/delete)")
    except Exception as e:
        fail("SeaweedFS S3 CRUD", str(e))


# ---------- 2. Dragonfly ----------
def test_dragonfly():
    try:
        import redis
        r = redis.Redis(host=DRAGONFLY_HOST, port=DRAGONFLY_PORT, socket_timeout=5)
        assert r.ping()
        r.set("lk:verify", "short-mem", ex=60)
        assert r.get("lk:verify") == b"short-mem"
        assert 55 < r.ttl("lk:verify") <= 60
        r.delete("lk:verify")
        ok("Dragonfly set/get/TTL")
    except Exception as e:
        fail("Dragonfly set/get/TTL", str(e))


# ---------- 3. Gravitino REST + S3 集成 ----------
def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_gravitino():
    base = f"{GRAVITINO_URI}/api"
    try:
        # metalake（幂等：先建，已存在则忽略）
        _req("POST", f"{base}/metalakes", {"name": METALAKE, "comment": "LakeMind MVP"})
        st, body = _req("GET", f"{base}/metalakes")
        names = [m["name"] for m in json.loads(body).get("metalakes", [])]
        assert METALAKE in names, f"metalake not found: {names}"

        # S3 桶
        import boto3
        from botocore.client import Config
        s3 = boto3.client(
            "s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_AK,
            aws_secret_access_key=S3_SK, region_name=S3_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        s3.create_bucket(Bucket="lakemind-filesets")
    except Exception as _e:
        from botocore.exceptions import ClientError
        if not (isinstance(_e, ClientError) and _e.response.get("Error", {}).get("Code")
                in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists")):
            fail("Gravitino->S3 fileset 集成", f"bucket: {_e}")
            return

    try:
        sw = "lakemind-seaweedfs:8333"
        cat_body = {
            "name": "cat_fs", "type": "fileset", "provider": "fileset",
            "comment": "verify fileset", "properties": {
                "location": "s3a://lakemind-filesets/",
                "s3-access-key-id": S3_AK, "s3-secret-access-key": S3_SK,
                "s3-endpoint": f"http://{sw}", "s3-region": S3_REGION,
                "s3-path-style-access": "true",
            },
        }
        _req("DELETE", f"{base}/metalakes/{METALAKE}/catalogs/cat_fs?force=true")
        st, body = _req("POST", f"{base}/metalakes/{METALAKE}/catalogs", cat_body)
        assert st == 200, f"catalog create {st}: {body}"

        # schema（幂等）
        _req("POST", f"{base}/metalakes/{METALAKE}/catalogs/cat_fs/schemas",
             {"name": "knowledge", "comment": "知识域"})
        # fileset
        st, body = _req("POST",
                        f"{base}/metalakes/{METALAKE}/catalogs/cat_fs/schemas/knowledge/filesets",
                        {"name": "docs", "storageLocation": "s3a://lakemind-filesets/knowledge/docs",
                         "comment": "文档RAG"})
        assert st == 200, f"fileset create {st}: {body}"

        # 验证 S3 实际写入
        time.sleep(1)
        objs = [o["Key"] for o in s3.list_objects_v2(Bucket="lakemind-filesets").get("Contents", [])]
        assert any(k.startswith("knowledge/docs") for k in objs), f"S3 not written: {objs}"
        ok("Gravitino->S3 fileset 集成", f"(S3 contents: {objs})")
    except Exception as e:
        fail("Gravitino->S3 fileset 集成", str(e))


if __name__ == "__main__":
    print("=== LakeMind 平台集成验证 ===")
    test_s3()
    test_dragonfly()
    test_gravitino()
    print(f"\n结果: {passed} 通过, {failed} 失败")
    sys.exit(1 if failed else 0)
