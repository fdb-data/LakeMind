from __future__ import annotations
from typing import Any
import pyarrow as pa
from pyiceberg.catalog import load_catalog


_TYPE_MAP_ARROW_TO_ICEBERG = {
    pa.string(): "StringType",
}


class IcebergTabularStorage:
    def __init__(self, catalog_name: str, warehouse: str, sql_uri: str, **kwargs):
        self._catalog_name = catalog_name
        self._warehouse = warehouse
        self._sql_uri = sql_uri
        self._catalog = None
        if warehouse.startswith("s3://"):
            parts = warehouse[5:].split("/", 1)
            self._bucket = parts[0]
            self._wh_path = parts[1] if len(parts) > 1 else ""
        else:
            self._bucket = ""
            self._wh_path = ""

    def _ensure(self):
        if self._catalog is None:
            s3_endpoint = self._sql_uri
            self._catalog = load_catalog(
                self._catalog_name,
                type="sql",
                uri=self._sql_uri,
                warehouse=self._warehouse,
                **{"s3.endpoint": _get_s3_endpoint(), "s3.access-key-id": "admin",
                   "s3.secret-access-key": "admin123456", "s3.region": "us-east-1"},
            )

    def ensure_namespace(self, namespace: str) -> None:
        self._ensure()
        try:
            self._catalog.create_namespace(namespace)
        except Exception:
            pass

    def list_namespaces(self) -> list[str]:
        self._ensure()
        try:
            return [str(ns) for ns in self._catalog.list_namespaces()]
        except Exception:
            return []

    def list_tables(self, namespace: str) -> list[str]:
        self._ensure()
        try:
            ids = self._catalog.list_tables(namespace)
            return [str(t[-1]) if isinstance(t, tuple) else str(t) for t in ids]
        except Exception:
            return []

    def table_exists(self, namespace: str, table: str) -> bool:
        self._ensure()
        try:
            self._catalog.load_table(f"{namespace}.{table}")
            return True
        except Exception:
            return False

    def create_table(self, namespace: str, table: str, schema: pa.Schema,
                     location: str | None = None) -> str:
        self._ensure()
        self.ensure_namespace(namespace)
        from ..._schema_convert import arrow_to_iceberg_schema
        iceberg_schema = arrow_to_iceberg_schema(schema)
        if location is None:
            location = f"s3://{self._bucket}/{self._wh_path}/{namespace}/{table}"
        t = self._catalog.create_table(
            identifier=f"{namespace}.{table}",
            schema=iceberg_schema,
            location=location,
        )
        return t.location()

    def append(self, namespace: str, table: str, data: pa.Table) -> int:
        self._ensure()
        t = self._catalog.load_table(f"{namespace}.{table}")
        t.append(data)
        return data.num_rows

    def overwrite(self, namespace: str, table: str, data: pa.Table) -> int:
        self._ensure()
        t = self._catalog.load_table(f"{namespace}.{table}")
        t.overwrite(data)
        return data.num_rows

    def scan(self, namespace: str, table: str, columns: list[str] | None = None,
             filter: str | None = None, limit: int | None = None) -> pa.Table:
        self._ensure()
        t = self._catalog.load_table(f"{namespace}.{table}")
        scan_builder = t.scan()
        if columns:
            scan_builder = scan_builder.select(*columns)
        result = scan_builder.to_arrow()
        if limit is not None:
            result = result.slice(0, limit)
        return result

    def describe(self, namespace: str, table: str) -> dict:
        self._ensure()
        t = self._catalog.load_table(f"{namespace}.{table}")
        schema = {field.name: str(field.field_type) for field in t.schema().fields}
        return {
            "name": f"{namespace}.{table}",
            "schema": schema,
            "columns": list(schema.keys()),
            "location": t.metadata_location,
        }

    def drop_table(self, namespace: str, table: str) -> None:
        self._ensure()
        self._catalog.drop_table(f"{namespace}.{table}")

    def health(self) -> bool:
        try:
            self._ensure()
            self._catalog.list_namespaces()
            return True
        except Exception:
            return False


def _get_s3_endpoint():
    import os
    return os.environ.get("S3_ENDPOINT", "http://lakemind-seaweedfs:8333")
