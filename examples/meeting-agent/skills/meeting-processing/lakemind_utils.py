import os
import json
import httpx

MS_URL = os.environ.get("MODEL_SERVING_URL", "http://lakemind-model-serving:10824")
MS_KEY = os.environ.get("MODELSERVING_API_KEY", "lakemind-modelserving-key")
SERVER_URL = os.environ.get("SERVER_API_URL", "http://lakemind-server-api:10823")
SERVER_KEY = os.environ.get("SERVER_API_KEY", os.environ.get("API_KEY", "lakemind-internal-api-key"))


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
