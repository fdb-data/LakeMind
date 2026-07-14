from __future__ import annotations
from enum import Enum


class Action(str, Enum):
    ASSET_CREATE = "asset:create"
    ASSET_READ = "asset:read"
    ASSET_UPDATE = "asset:update"
    ASSET_DELETE = "asset:delete"
    KNOWLEDGE_INGEST = "knowledge:ingest"
    KNOWLEDGE_SEARCH = "knowledge:search"
    KNOWLEDGE_REINDEX = "knowledge:reindex"
    SKILL_REGISTER = "skill:register"
    SKILL_PUBLISH = "skill:publish"
    SKILL_EXECUTE = "skill:execute"
    SKILL_REVOKE = "skill:revoke"
    SKILL_READ = "skill:read"
    MEMORY_ADD = "memory:add"
    MEMORY_READ = "memory:read"
    MEMORY_UPDATE = "memory:update"
    MEMORY_DELETE = "memory:delete"
    MEMORY_CLEAR = "memory:clear"
    JOB_SUBMIT = "job:submit"
    JOB_READ = "job:read"
    JOB_CANCEL = "job:cancel"
    JOB_RETRY = "job:retry"
    MODEL_READ = "model:read"
    MODEL_CONFIGURE = "model:configure"
    MODEL_USE = "model:use"
    SECRET_USE = "secret:use"
    SECRET_ROTATE = "secret:rotate"
    OPERATION_REQUEST = "operation:request"
    OPERATION_APPROVE = "operation:approve"
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    CONFIG_ACTIVATE = "config:activate"
    AUDIT_READ = "audit:read"


ALL_ACTIONS = [a.value for a in Action]
