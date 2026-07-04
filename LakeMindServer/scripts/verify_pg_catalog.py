"""Step 2: 验证 PyIceberg SQL catalog 连接 PostgreSQL。"""
import sys
import pyarrow as pa
from pyiceberg.catalog import load_catalog

PG_URI = "postgresql+psycopg2://lakemind:lakemind_pass@localhost:5432/lakemind"
S3_ENDPOINT = "http://localhost:8333"
S3_KEY = "admin"
S3_SECRET = "admin123456"

passed = failed = 0
def ok(n, d=""):
    global passed; passed += 1; print(f"  [PASS] {n} {d}")
def fail(n, d=""):
    global failed; failed += 1; print(f"  [FAIL] {n} {d}")

print("== Step 2: PyIceberg + PostgreSQL Catalog ==")

# 1. 加载 catalog
try:
    cat = load_catalog(
        "lakemind",
        **{
            "type": "sql",
            "uri": PG_URI,
            "warehouse": "s3://lakemind-iceberg/warehouse",
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": S3_KEY,
            "s3.secret-access-key": S3_SECRET,
            "s3.region": "us-east-1",
        },
    )
    ok("load_catalog (PostgreSQL SQL catalog)")
except Exception as e:
    fail("load_catalog", str(e)[:200])
    sys.exit(1)

# 2. 创建 namespace
ns = "test_pg"
try:
    cat.create_namespace(ns)
    ok(f"create_namespace({ns})")
except Exception:
    try:
        cat.drop_namespace(ns)
    except Exception:
        pass
    cat.create_namespace(ns)
    ok(f"create_namespace({ns}) (recreated)")

# 3. 创建表
table_name = f"{ns}.test_table"
try:
    try:
        cat.drop_table(table_name)
    except Exception:
        pass
    schema = pa.schema([
        pa.field("id", pa.int64()),
        pa.field("name", pa.string()),
        pa.field("value", pa.float64()),
    ])
    t = cat.create_table(
        table_name,
        schema=schema,
        location=f"s3://lakemind-iceberg/warehouse/{ns}/test_table",
    )
    ok(f"create_table({table_name})")
except Exception as e:
    fail("create_table", str(e)[:200])
    sys.exit(1)

# 4. 写入数据
try:
    data = pa.table({
        "id": [1, 2, 3],
        "name": ["alpha", "beta", "gamma"],
        "value": [1.1, 2.2, 3.3],
    })
    t.append(data)
    ok(f"append({data.num_rows} rows)")
except Exception as e:
    fail("append", str(e)[:200])

# 5. 读取数据
try:
    result = t.scan().to_arrow()
    assert result.num_rows == 3, f"expected 3 rows, got {result.num_rows}"
    assert "alpha" in result.column("name").to_pylist()
    ok(f"scan() -> {result.num_rows} rows")
except Exception as e:
    fail("scan", str(e)[:200])

# 6. 列表
try:
    tables = cat.list_tables(ns)
    assert "test_table" in [t[-1] if isinstance(t, tuple) else str(t).split(".")[-1] for t in tables]
    ok(f"list_tables -> {tables}")
except Exception as e:
    fail("list_tables", str(e)[:200])

# 7. 并发写入测试（模拟多进程）
try:
    t2 = cat.load_table(table_name)
    data2 = pa.table({
        "id": [4, 5],
        "name": ["delta", "epsilon"],
        "value": [4.4, 5.5],
    })
    t2.append(data2)
    result = t2.scan().to_arrow()
    assert result.num_rows == 5, f"expected 5 rows after concurrent append, got {result.num_rows}"
    ok(f"concurrent append -> {result.num_rows} rows total")
except Exception as e:
    fail("concurrent append", str(e)[:200])

# 8. 清理
try:
    cat.drop_table(table_name)
    cat.drop_namespace(ns)
    ok("cleanup (drop table + namespace)")
except Exception as e:
    fail("cleanup", str(e)[:200])

print(f"\n[verify_pg_catalog] {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
