"""SeaweedFS S3 兼容客户端（boto3，连接池）。"""
from __future__ import annotations

from typing import IO, Any

from ..config import S3Cfg

__all__ = ["S3Client"]


class S3Client:
    def __init__(self, cfg: S3Cfg) -> None:
        self._cfg = cfg
        self._client = None

    def _ensure(self):
        if self._client is None:
            import boto3
            from botocore.client import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self._cfg.endpoint,
                aws_access_key_id=self._cfg.access_key,
                aws_secret_access_key=self._cfg.secret_key,
                region_name=self._cfg.region,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        return self._client

    def ensure_bucket(self, bucket: str) -> None:
        c = self._ensure()
        try:
            c.head_bucket(Bucket=bucket)
        except Exception:
            c.create_bucket(Bucket=bucket)

    def put(self, bucket: str, key: str, body: bytes | str) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self._ensure().put_object(Bucket=bucket, Key=key, Body=data)

    def get(self, bucket: str, key: str) -> bytes:
        return self._ensure().get_object(Bucket=bucket, Key=key)["Body"].read()

    def exists(self, bucket: str, key: str) -> bool:
        c = self._ensure()
        try:
            c.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def list(self, bucket: str, prefix: str = "") -> list[str]:
        resp = self._ensure().list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [o["Key"] for o in resp.get("Contents", [])]

    def close(self) -> None:
        self._client = None
