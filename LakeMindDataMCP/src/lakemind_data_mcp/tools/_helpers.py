"""工具层公共辅助：scope 校验、审计包装。"""
from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable

from ..context import get_identity
from ..security.audit import audit_log

__all__ = ["require_scope", "audited"]


def require_scope(scope: str) -> None:
    """校验当前 Identity 持有给定 scope，否则抛 PermissionError。"""
    ident = get_identity()
    if not ident.has_scope(scope):
        raise PermissionError(f"missing required scope: {scope}")


def audited(redact_keys: list[str]) -> Callable:

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            audit_log(fn.__name__, _clean_args(args, fn), redact_keys)
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def _clean_args(args: tuple, fn: Callable) -> dict[str, Any]:
    # 仅保留关键字参数用于审计（位置参数按参数名映射）
    try:
        import inspect

        sig = inspect.signature(fn)
        names = list(sig.parameters.keys())
        return {names[i]: a for i, a in enumerate(args) if i < len(names)}
    except Exception:
        return {}
