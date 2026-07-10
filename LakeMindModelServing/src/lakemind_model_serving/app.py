from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import load_config
from .gateway import ModelGateway
from .registry import ModelRegistry
from .services.embedding import EmbeddingService
from .services.asr import ASRService
from .api import chat, embeddings, audio, models, health

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    cfg = load_config()

    app = FastAPI(title="LakeMindModelServing", version="0.1.0")
    app.state.api_key = cfg.server.api_key

    registry = ModelRegistry(
        host=cfg.registry.host,
        port=cfg.registry.port,
        db=cfg.registry.db,
        user=cfg.registry.user,
        password=cfg.registry.password,
    )
    app.state.registry = registry

    gateway = ModelGateway(
        providers=cfg.llm_providers,
        gateway_config={
            "default_chat_model": cfg.gateway.default_chat_model,
            "default_embed_model": cfg.gateway.default_embed_model,
            "fallback": cfg.gateway.fallback,
            "cache": cfg.gateway.cache,
        },
    )
    app.state.gateway = gateway

    for m in registry.list_active():
        if m["type"] == "llm":
            gateway.register_model({
                "model_id": m["model_id"],
                "type": m["type"],
                "provider": m["provider"],
                "litellm_model": m.get("litellm_model", ""),
                "api_key": m.get("api_key", ""),
                "base_url": m.get("base_url", ""),
                "tags": m.get("tags", []),
                "context_window": m.get("context_window", 0),
            })

    if cfg.embedding.built_in.enabled:
        embedding_service = EmbeddingService(
            model_name=cfg.embedding.built_in.model,
            dim=cfg.embedding.built_in.dim,
            cache_dir=cfg.embedding.built_in.cache_dir,
        )
        app.state.embedding_service = embedding_service
    else:
        app.state.embedding_service = None

    if cfg.asr.built_in.enabled:
        asr_service = ASRService(
            model_name=cfg.asr.built_in.model,
            language=cfg.asr.built_in.language,
            cache_dir=cfg.asr.built_in.cache_dir,
        )
        app.state.asr_service = asr_service
    else:
        app.state.asr_service = None

    app.include_router(chat.router, tags=["chat"])
    app.include_router(embeddings.router, tags=["embeddings"])
    app.include_router(audio.router, tags=["audio"])
    app.include_router(models.router, tags=["models"])
    app.include_router(health.router, tags=["health"])

    return app
