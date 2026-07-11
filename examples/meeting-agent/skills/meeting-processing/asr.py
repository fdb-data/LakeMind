import os
import json
import httpx
from lakemind_utils import download_from_s3, upload_to_s3, MS_URL, MS_KEY


def main():
    params = json.loads(os.environ["RAY_JOB_PARAMS"])
    chunk_uri = params["chunk_uri"]
    result_uri = params["result_uri"]

    audio = download_from_s3(chunk_uri)

    resp = httpx.post(
        f"{MS_URL}/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {MS_KEY}"},
        files={"file": ("audio.wav", audio, "audio/wav")},
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()

    output = {"text": result.get("text", ""), "segments": result.get("segments", [])}
    upload_to_s3(result_uri, json.dumps(output, ensure_ascii=False))
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
