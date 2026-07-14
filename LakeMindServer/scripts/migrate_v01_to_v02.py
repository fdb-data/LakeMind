"""WP9-T04: Migrate v0.1.0 data to v0.2.0 schema."""
import os
import sys
import json
import psycopg2
import yaml

PG_DSN = os.environ.get("DATABASE_URL", "postgresql://lakemind:lakemind@localhost:5432/lakemind")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:8333")


def migrate_v01_to_v02():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    print("=== v0.1.0 -> v0.2.0 Migration ===")

    print("[1/5] Migrating S3 knowledge files -> assets...")
    cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'objects'")
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT id, tenant_id, key, size FROM objects WHERE content_type LIKE 'text/%' OR content_type LIKE 'application/%'")
        for row in cur.fetchall():
            obj_id, tenant_id, key, size = row
            cur.execute(
                "INSERT INTO assets (asset_id, tenant_id, asset_type, name, status, source_uri) "
                "VALUES (%s, %s, 'knowledge', %s, 'READY', %s) ON CONFLICT DO NOTHING",
                (f"knowledge_{obj_id}", tenant_id, key.split("/")[-1], f"s3://{key}"),
            )
        print(f"  Migrated knowledge files")
    else:
        print("  No objects table found, skipping")

    print("[2/5] Migrating memory records -> assets + memory_meta...")
    cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'memory_records'")
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT id, tenant_id, content, metadata FROM memory_records")
        for row in cur.fetchall():
            mem_id, tenant_id, content, metadata = row
            asset_id = f"memory_{mem_id}"
            cur.execute(
                "INSERT INTO assets (asset_id, tenant_id, asset_type, name, status, metadata) "
                "VALUES (%s, %s, 'memory', %s, 'READY', %s) ON CONFLICT DO NOTHING",
                (asset_id, tenant_id, f"memory_{mem_id}", json.dumps(metadata or {})),
            )
            cur.execute(
                "INSERT INTO memory_meta (asset_id, memory_type, content_hash) "
                "VALUES (%s, 'semantic', %s) ON CONFLICT DO NOTHING",
                (asset_id, hash(content) % (10**18)),
            )
        print(f"  Migrated memory records")
    else:
        print("  No memory_records table found, skipping")

    print("[3/5] Migrating models.yaml -> model_definitions...")
    models_yaml = os.environ.get("MODELS_YAML_PATH", "config/models.yaml")
    if os.path.exists(models_yaml):
        with open(models_yaml, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        for model_def in config.get("models", []):
            cur.execute(
                "INSERT INTO model_definitions (model_id, name, model_type, capabilities, provider_family) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (f"mdl_{model_def['name']}", model_def["name"], model_def["type"],
                 json.dumps(model_def.get("capabilities", [])), model_def["provider_family"]),
            )
        print(f"  Migrated {len(config.get('models', []))} models")
    else:
        print(f"  {models_yaml} not found, skipping")

    print("[4/5] Migrating static tokens -> v2_tokens...")
    cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'tokens'")
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT id, tenant_id, key_hash, scopes FROM tokens")
        for row in cur.fetchall():
            tok_id, tenant_id, key_hash, scopes = row
            cur.execute(
                "INSERT INTO v2_tokens (token_id, principal_id, tenant_id, token_hash, scopes, status) "
                "VALUES (%s, %s, %s, %s, %s, 'active') ON CONFLICT DO NOTHING",
                (f"v2tok_{tok_id}", f"principal_{tenant_id}", tenant_id, key_hash, json.dumps(scopes or [])),
            )
        print(f"  Migrated tokens")
    else:
        print("  No tokens table found, skipping")

    print("[5/5] Migrating .env -> config_values...")
    env_mapping = {
        "LAKEMIND_EMBEDDING_MODEL": "embedding.default_model",
        "LAKEMIND_EMBEDDING_DIM": "embedding.default_dim",
        "LAKEMIND_LLM_MODEL": "llm.default_model",
    }
    for env_key, config_key in env_mapping.items():
        val = os.environ.get(env_key)
        if val:
            cur.execute(
                "INSERT INTO config_values (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (config_key, val),
            )
    print(f"  Migrated env config")

    conn.commit()
    cur.close()
    conn.close()
    print("=== Migration Complete ===")


if __name__ == "__main__":
    migrate_v01_to_v02()
