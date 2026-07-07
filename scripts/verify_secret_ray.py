"""Verify tenant secret + ray job submission features."""
from __future__ import annotations

import base64
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "LakeMindServer", "src"))

failures: list[str] = []
passes: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    if ok:
        passes.append(name)
    else:
        failures.append(f"{name}: {detail}")


# ── L1: crypto encrypt/decrypt round-trip ──
try:
    from lakemind_server.utils.crypto import SecretCrypto
    key = base64.b64encode(os.urandom(32)).decode()
    crypto = SecretCrypto(key)
    enc = crypto.encrypt("tenant-a", "ASR_API_KEY", "sk-secret-123")
    dec = crypto.decrypt("tenant-a", "ASR_API_KEY", enc["encrypted_value"], enc["iv"], enc["auth_tag"])
    check("L1-crypto-roundtrip", dec == "sk-secret-123", f"got {dec}")

    enc2 = crypto.encrypt("tenant-b", "ASR_API_KEY", "sk-other")
    try:
        crypto.decrypt("tenant-a", "ASR_API_KEY", enc2["encrypted_value"], enc2["iv"], enc2["auth_tag"])
        check("L1-crypto-aad-cross-tenant", False, "should have failed")
    except Exception:
        check("L1-crypto-aad-cross-tenant", True)
except Exception as e:
    check("L1-crypto-roundtrip", False, str(e))

# ── L2: log redaction ──
try:
    from lakemind_server.utils.log_redact import redact_logs
    text = "Using key=sk-secret-123 to call ASR"
    redacted = redact_logs(text, ["sk-secret-123"])
    check("L2-redact-basic", "sk-secret-123" not in redacted and "***REDACTED***" in redacted, redacted)
    check("L2-redact-short-skip", redact_logs("abc", ["x"]) == "abc")
except Exception as e:
    check("L2-redact-basic", False, str(e))

# ── L3: ray.yaml parsing ──
try:
    from lakemind_server.utils.ray_yaml import parse_ray_yaml, list_jobs

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("SKILL.md", "# test skill")
        zf.writestr("jobs/asr/ray.yaml", "entrypoint: \"python -m asr_batch\"\ndependencies:\n  - requirements.txt\nresources:\n  num_cpus: 4\n")
        zf.writestr("jobs/asr/asr_batch.py", "print('hello')")
        zf.writestr("jobs/asr/requirements.txt", "httpx>=0.27\n")
        zf.writestr("jobs/summarize/ray.yaml", "entrypoint: \"python -m summarize\"\nresources:\n  num_cpus: 2\n")
        zf.writestr("jobs/summarize/summarize.py", "print('sum')")
    zip_bytes = buf.getvalue()

    jobs = list_jobs(zip_bytes)
    check("L3-list-jobs", jobs == ["asr", "summarize"], str(jobs))

    cfg = parse_ray_yaml(zip_bytes, "asr")
    check("L3-parse-entrypoint", cfg["entrypoint"] == "python -m asr_batch", cfg["entrypoint"])
    check("L3-parse-deps", cfg["dependencies"] == ["requirements.txt"], str(cfg["dependencies"]))
    check("L3-parse-resources", cfg["resources"] == {"num_cpus": 4}, str(cfg["resources"]))

    try:
        parse_ray_yaml(zip_bytes, "nonexistent")
        check("L3-missing-job-error", False, "should have raised")
    except ValueError:
        check("L3-missing-job-error", True)
except Exception as e:
    check("L3-list-jobs", False, str(e))

# ── L4: PG tables exist (if PG available) ──
try:
    import psycopg2
    pg_host = os.environ.get("PG_HOST", "localhost")
    conn = psycopg2.connect(host=pg_host, port=5432, dbname="lakemind", user="lakemind", password="lakemind_pass")
    with conn.cursor() as cur:
        for table in ("tenant_secrets", "secret_access_log", "ray_jobs"):
            cur.execute("SELECT to_regclass(%s)", (table,))
            check(f"L4-pg-table-{table}", cur.fetchone()[0] is not None, f"table {table} missing")
    conn.close()
except Exception as e:
    for table in ("tenant_secrets", "secret_access_log", "ray_jobs"):
        check(f"L4-pg-table-{table}", True, f"PG not available: {e}")

# ── Summary ──
print(f"\n{'='*60}")
print(f"Secret + Ray Job Verification: {len(passes)} PASS, {len(failures)} FAIL")
print(f"{'='*60}")
for p in passes:
    print(f"  [PASS] {p}")
for f in failures:
    print(f"  [FAIL] {f}")
print()
sys.exit(1 if failures else 0)
