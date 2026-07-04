"""OpenAI 兼容的 mock embedding 测试服务（测试夹具，非生产代码）。

返回基于 SHA256 的确定性向量，dim 由请求体不携带时默认 512。
生产环境应指向真实外部 embedding 服务，不使用本文件。

运行：python scripts/mock_embedding_server.py --port 8081
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import uuid
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def _embed(text: str, dim: int) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(dim):
        b = h[(i * 4) % len(h) : (i * 4) % len(h) + 4]
        if len(b) < 4:
            b = b + h[: 4 - len(b)]
        vec.append(struct.unpack("f", b)[0])
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec] if norm > 0 else vec


async def embeddings(request: Request) -> JSONResponse:
    body: dict[str, Any] = await request.json()
    inputs = body["input"]
    if isinstance(inputs, str):
        inputs = [inputs]
    model = body.get("model", "mock")
    dim = body.get("dimensions", 512)
    data = [
        {"object": "embedding", "index": i, "embedding": _embed(str(t), dim)}
        for i, t in enumerate(inputs)
    ]
    return JSONResponse({"object": "list", "data": data, "model": model, "usage": {}})


async def models(request: Request) -> JSONResponse:
    return JSONResponse({"object": "list", "data": [{"id": "mock", "object": "model"}]})


def build_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/v1/embeddings", embeddings, methods=["POST"]),
            Route("/v1/models", models, methods=["GET"]),
            Route("/health", lambda r: JSONResponse({"status": "ok"}), methods=["GET"]),
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8081)
    args = ap.parse_args()
    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
