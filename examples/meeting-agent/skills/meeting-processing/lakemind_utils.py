import os
import json
import time
import httpx

MS_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
SERVER_URL = os.environ.get("SERVER_API_URL", "http://lakemind-server-api:10823")
SERVER_KEY = os.environ.get("SERVER_API_KEY", os.environ.get("API_KEY", "lakemind-internal-api-key"))
EMBED_MODEL = os.environ.get("EMBED_MODEL", "jina-embeddings-v2-base-zh")


def download_from_s3(uri: str) -> bytes:
    from urllib.parse import urlparse
    p = urlparse(uri)
    bucket = p.netloc
    key = p.path.lstrip("/")
    url = f"{SERVER_URL}/api/v1/storage/objects/{bucket}/{key}"
    resp = httpx.get(url, headers={"Authorization": f"Bearer {SERVER_KEY}"}, timeout=60)
    resp.raise_for_status()
    return resp.content


def upload_to_s3(uri: str, data: bytes | str):
    from urllib.parse import urlparse
    if isinstance(data, str):
        data = data.encode()
    p = urlparse(uri)
    bucket = p.netloc
    key = p.path.lstrip("/")
    url = f"{SERVER_URL}/api/v1/storage/objects/{bucket}/{key}"
    resp = httpx.put(url, content=data, headers={"Authorization": f"Bearer {SERVER_KEY}"}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def llm_chat(system_prompt: str, user_content: str, model: str = "deepseek-v4-flash") -> str:
    resp = httpx.post(
        f"{MS_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {MS_KEY}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def asr(audio: bytes, filename: str = "audio.wav") -> dict:
    resp = httpx.post(
        f"{MS_URL}/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {MS_KEY}"},
        files={"file": (filename, audio, "audio/wav")},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def embed(text: str) -> list[float]:
    resp = httpx.post(
        f"{MS_URL}/v1/embeddings",
        headers={"Authorization": f"Bearer {MS_KEY}"},
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def ingest_knowledge(kb_name: str, concepts: list[dict], tenant_id: str = "default"):
    db = f"tenant_{tenant_id}"
    table = f"kb_{kb_name}"
    data = []
    for concept in concepts:
        fm = concept.get("frontmatter", {})
        title = fm.get("title", concept.get("title", ""))
        body = concept.get("body", "")
        text = f"{title}\n{body}"
        vec = embed(text)
        data.append({
            "concept_id": fm.get("resource", f"{kb_name}_{int(time.time()*1000)}"),
            "type": fm.get("type", "Concept"),
            "title": title,
            "description": body[:500],
            "tags": fm.get("tags", []),
            "s3_uri": "",
            "vector": vec,
            "created_at": time.time(),
        })

    resp = httpx.post(
        f"{SERVER_URL}/api/v1/storage/vectors/{db}",
        headers={"Authorization": f"Bearer {SERVER_KEY}"},
        json={"name": table, "data": data, "mode": "append"},
        timeout=30,
    )
    if resp.status_code == 500:
        resp = httpx.post(
            f"{SERVER_URL}/api/v1/storage/vectors/{db}",
            headers={"Authorization": f"Bearer {SERVER_KEY}"},
            json={"name": table, "data": data, "mode": "overwrite"},
            timeout=30,
        )
    resp.raise_for_status()
    return {"kb_name": kb_name, "ingested": len(data)}
