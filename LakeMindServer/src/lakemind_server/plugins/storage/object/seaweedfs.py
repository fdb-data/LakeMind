from __future__ import annotations
import boto3
from botocore.client import Config as BotoConfig


class SeaweedFSStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str,
                 region: str = "us-east-1", path_style: bool = True, **kwargs):
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._path_style = path_style
        self._client = None

    def _ensure(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
                config=BotoConfig(signature_version="s3v4",
                                  s3={"addressing_style": "path" if self._path_style else "auto"}),
            )

    def ensure_bucket(self, bucket: str) -> None:
        self._ensure()
        try:
            self._client.head_bucket(Bucket=bucket)
        except Exception:
            self._client.create_bucket(Bucket=bucket)

    def put(self, bucket: str, key: str, body: bytes) -> None:
        self._ensure()
        self._client.put_object(Bucket=bucket, Key=key, Body=body)

    def get(self, bucket: str, key: str) -> bytes:
        self._ensure()
        return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def delete(self, bucket: str, key: str) -> None:
        self._ensure()
        self._client.delete_object(Bucket=bucket, Key=key)

    def exists(self, bucket: str, key: str) -> bool:
        self._ensure()
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def list(self, bucket: str, prefix: str = "", limit: int = 1000) -> list[str]:
        self._ensure()
        resp = self._client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=limit)
        return [obj["Key"] for obj in resp.get("Contents", [])]

    def health(self) -> bool:
        try:
            self._ensure()
            self._client.list_buckets()
            return True
        except Exception:
            return False
