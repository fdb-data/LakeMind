from __future__ import annotations
import json
import ulid
from datetime import datetime, timezone
from ..db import execute, execute_one


class SearchService:

    @staticmethod
    def upsert_projection(object_type: str, object_id: str, title: str,
                          scope_type: str = "TENANT", scope_id: str | None = None,
                          subtitle: str | None = None, keywords: str | None = None,
                          visibility: str = "tenant", owner_id: str | None = None) -> None:
        execute(
            "INSERT INTO search_projections (object_type, object_id, scope_type, scope_id, "
            "title, subtitle, keywords, visibility, owner_id, tsv, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "to_tsvector('simple', %s), %s) "
            "ON CONFLICT (object_type, object_id) DO UPDATE SET "
            "scope_type = EXCLUDED.scope_type, scope_id = EXCLUDED.scope_id, "
            "title = EXCLUDED.title, subtitle = EXCLUDED.subtitle, "
            "keywords = EXCLUDED.keywords, visibility = EXCLUDED.visibility, "
            "owner_id = EXCLUDED.owner_id, tsv = EXCLUDED.tsv, "
            "updated_at = EXCLUDED.updated_at",
            (object_type, object_id, scope_type, scope_id,
             title, subtitle, keywords, visibility, owner_id,
             f"{title} {subtitle or ''} {keywords or ''}",
             datetime.now(timezone.utc)),
        )

    @staticmethod
    def delete_projection(object_type: str, object_id: str) -> None:
        execute(
            "DELETE FROM search_projections WHERE object_type = %s AND object_id = %s",
            (object_type, object_id),
        )

    @staticmethod
    def search(q: str, object_types: list[str] | None = None,
               scope_type: str | None = None, scope_id: str | None = None,
               platform_admin: bool = False,
               page: int = 1, page_size: int = 20) -> dict:
        conditions = []
        params: list = []

        exact = execute(
            "SELECT object_type, object_id, scope_type, scope_id, title, subtitle, updated_at "
            "FROM search_projections WHERE object_id = %s "
            + ("AND object_type = ANY(%s)" if object_types else ""),
            ([q] + ([object_types] if object_types else [])),
        ) if q else []

        ts_conditions = ["tsv @@ plainto_tsquery('simple', %s)"]
        params.append(q)
        trgm_conditions = ["title %% %s"]
        params.append(q)

        if object_types:
            placeholders = ", ".join(["%s"] * len(object_types))
            ts_conditions.append(f"object_type IN ({placeholders})")
            trgm_conditions.append(f"object_type IN ({placeholders})")
            params.extend(object_types)
            params.extend(object_types)

        if not platform_admin:
            if scope_type and scope_id:
                ts_conditions.append("scope_type = %s AND scope_id = %s")
                trgm_conditions.append("scope_type = %s AND scope_id = %s")
                params.extend([scope_type, scope_id])
            elif scope_type:
                ts_conditions.append("scope_type = %s")
                trgm_conditions.append("scope_type = %s")
                params.append(scope_type)

        ts_where = " AND ".join(ts_conditions)
        trgm_where = " AND ".join(trgm_conditions)

        offset = (page - 1) * page_size
        items = execute(
            f"SELECT DISTINCT ON (object_type, object_id) "
            f"object_type, object_id, scope_type, scope_id, title, subtitle, updated_at "
            f"FROM search_projections WHERE ({ts_where}) OR ({trgm_where}) "
            f"ORDER BY object_type, object_id, updated_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        authorized = []
        for item in items:
            if platform_admin:
                authorized.append(item)
            elif item["scope_type"] == "TENANT" and scope_id and item["scope_id"] == scope_id:
                authorized.append(item)
            elif item["scope_type"] == "PLATFORM" and scope_type == "PLATFORM":
                authorized.append(item)

        groups: dict[str, int] = {}
        for item in authorized:
            groups[item["object_type"]] = groups.get(item["object_type"], 0) + 1

        return {
            "items": authorized,
            "total": len(authorized),
            "page": page,
            "page_size": page_size,
            "groups": groups,
        }
