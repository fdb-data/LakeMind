"""Seed 4 Model Profiles for Meeting Agent into LakeMind Server."""
from __future__ import annotations
import asyncio
import os
import sys
import httpx

SERVER_URL = os.environ.get("SERVER_API_URL", "http://localhost:10823").rstrip("/")
API_KEY = os.environ.get("SERVER_API_KEY", "")
TENANT_ID = os.environ.get("TENANT_ID", "examples-meeting-agent")
MS_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")

MODELS = [
    {
        "name": "whisper-large-v3-turbo",
        "model_type": "asr",
        "capabilities": ["transcription"],
        "provider_family": "faster-whisper",
        "modalities": ["audio"],
        "metadata": {"description": "ASR for meeting agent"},
    },
    {
        "name": "deepseek-v4-flash",
        "model_type": "llm",
        "capabilities": ["chat", "completion"],
        "provider_family": "deepseek",
        "context_length": 64000,
        "modalities": ["text"],
        "metadata": {"description": "LLM for minutes + knowledge extract"},
    },
    {
        "name": "jina-embeddings-v2-base-zh",
        "model_type": "embedding",
        "capabilities": ["embedding"],
        "provider_family": "fastembed",
        "embedding_dim": 768,
        "modalities": ["text"],
        "metadata": {"description": "Embedding for meeting knowledge"},
    },
]

DEPLOYMENTS = [
    {"model_name": "whisper-large-v3-turbo", "provider": "faster-whisper", "endpoint": f"{MS_URL}/v1/audio/transcriptions", "secret_ref": "modelserving-key", "priority": 100},
    {"model_name": "deepseek-v4-flash", "provider": "deepseek", "endpoint": f"{MS_URL}/v1/chat/completions", "secret_ref": "modelserving-key", "priority": 100},
    {"model_name": "jina-embeddings-v2-base-zh", "provider": "fastembed", "endpoint": f"{MS_URL}/v1/embeddings", "secret_ref": "modelserving-key", "priority": 100},
]

PROFILES = [
    {"name": "meeting-asr", "description": "ASR for meeting transcription", "deployment_model": "whisper-large-v3-turbo"},
    {"name": "meeting-minutes", "description": "LLM for meeting minutes", "deployment_model": "deepseek-v4-flash"},
    {"name": "meeting-knowledge-extract", "description": "LLM for knowledge extraction", "deployment_model": "deepseek-v4-flash"},
    {"name": "meeting-embedding", "description": "Embedding for meeting knowledge", "deployment_model": "jina-embeddings-v2-base-zh"},
]


async def main():
    headers = {"Authorization": f"Bearer {API_KEY}", "X-Tenant-Id": TENANT_ID}
    async with httpx.AsyncClient(base_url=SERVER_URL, headers=headers, timeout=30) as client:
        existing_models = (await client.get("/api/v1/models/definitions")).json()
        existing_names = {m["name"] for m in existing_models}

        model_ids = {}
        for m in MODELS:
            if m["name"] in existing_names:
                for em in existing_models:
                    if em["name"] == m["name"]:
                        model_ids[m["name"]] = em["model_id"]
                print(f"  [SKIP] model {m['name']} exists")
                continue
            resp = await client.post("/api/v1/models/definitions", json=m)
            if resp.status_code == 200:
                model_ids[m["name"]] = resp.json()["model_id"]
                print(f"  [OK] created model {m['name']}")
            else:
                print(f"  [FAIL] model {m['name']}: {resp.status_code} {resp.text}")

        existing_deps = (await client.get("/api/v1/models/deployments")).json()
        dep_ids = {}
        for d in DEPLOYMENTS:
            mid = model_ids.get(d["model_name"])
            if not mid:
                continue
            match = next((ed for ed in existing_deps if ed.get("model_id") == mid and ed.get("endpoint") == d["endpoint"]), None)
            if match:
                dep_ids[d["model_name"]] = match["deployment_id"]
                print(f"  [SKIP] deployment for {d['model_name']} exists")
                continue
            body = {"model_id": mid, "provider": d["provider"], "endpoint": d["endpoint"], "secret_ref": d["secret_ref"], "priority": d["priority"]}
            resp = await client.post("/api/v1/models/deployments", json=body)
            if resp.status_code == 200:
                dep_id = resp.json()["deployment_id"]
                dep_ids[d["model_name"]] = dep_id
                await client.post(f"/api/v1/models/deployments/{dep_id}/enable")
                print(f"  [OK] created+enabled deployment for {d['model_name']}")
            else:
                print(f"  [FAIL] deployment {d['model_name']}: {resp.status_code} {resp.text}")

        existing_profiles = (await client.get("/api/v1/models/profiles")).json()
        existing_profile_names = {p["name"] for p in existing_profiles}

        for p in PROFILES:
            if p["name"] in existing_profile_names:
                print(f"  [SKIP] profile {p['name']} exists")
                continue
            resp = await client.post("/api/v1/models/profiles", json={"name": p["name"], "description": p["description"]})
            if resp.status_code != 200:
                print(f"  [FAIL] profile {p['name']}: {resp.status_code} {resp.text}")
                continue
            print(f"  [OK] created profile {p['name']}")

            dep_id = dep_ids.get(p["deployment_model"])
            if not dep_id:
                print(f"  [WARN] no deployment for {p['name']}")
                continue
            route_body = {"profile_name": p["name"], "deployment_id": dep_id, "priority": 100}
            rresp = await client.post("/api/v1/models/routes", json=route_body)
            if rresp.status_code == 200:
                print(f"  [OK] route {p['name']} -> {dep_id}")
            else:
                print(f"  [FAIL] route {p['name']}: {rresp.status_code} {rresp.text}")

        print("\n--- Verify ---")
        for p in PROFILES:
            resp = await client.post("/api/v1/models/profiles/resolve", json={"profile_name": p["name"]})
            if resp.status_code == 200:
                print(f"  [OK] resolve {p['name']}: {resp.json().get('deployment_id')}")
            else:
                print(f"  [FAIL] resolve {p['name']}: {resp.status_code}")


if __name__ == "__main__":
    asyncio.run(main())
