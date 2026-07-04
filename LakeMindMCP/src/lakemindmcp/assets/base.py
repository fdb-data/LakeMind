"""Asset 抽象基类。P3 实现。"""
from __future__ import annotations

from abc import ABC

__all__ = ["Asset"]


class Asset(ABC):
    """资产抽象：与引擎无关的能力接口。"""
