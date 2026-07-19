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
    TENANT_CREATE = "tenant:create"
    TENANT_MANAGE = "tenant:manage"
    OBS_VIEW = "obs:view"
    SEARCH_GLOBAL = "search:global"


ALL_ACTIONS = [a.value for a in Action]


class Capability(str, Enum):
    PLATFORM_ADMIN = "platform:admin"
    TENANT_CREATE = "tenant:create"
    TENANT_SUSPEND = "tenant:suspend"
    TENANT_ARCHIVE = "tenant:archive"
    PLATFORM_VIEW_ALL = "platform:view_all"
    TENANT_MANAGE = "tenant:manage"
    TENANT_VIEW = "tenant:view"
    ASSET_MANAGE = "asset:manage"
    ASSET_VIEW = "asset:view"
    JOB_SUBMIT = "job:submit"
    JOB_MANAGE = "job:manage"
    JOB_VIEW = "job:view"
    MODEL_CONFIGURE = "model:configure"
    MODEL_VIEW = "model:view"
    CONFIG_WRITE = "config:write"
    CONFIG_ACTIVATE = "config:activate"
    CONFIG_VIEW = "config:view"
    OPERATION_REQUEST = "operation:request"
    OPERATION_APPROVE = "operation:approve"
    OPERATION_VIEW = "operation:view"
    OBS_VIEW = "obs:view"
    OBS_MANAGE = "obs:manage"
    AUDIT_VIEW = "audit:view"
    SEARCH_GLOBAL = "search:global"
    STEWARD_CHAT = "steward:chat"


ACTION_TO_CAPABILITY: dict[Action, Capability] = {
    Action.ASSET_CREATE: Capability.ASSET_MANAGE,
    Action.ASSET_READ: Capability.ASSET_VIEW,
    Action.ASSET_UPDATE: Capability.ASSET_MANAGE,
    Action.ASSET_DELETE: Capability.ASSET_MANAGE,
    Action.KNOWLEDGE_INGEST: Capability.ASSET_MANAGE,
    Action.KNOWLEDGE_SEARCH: Capability.ASSET_VIEW,
    Action.KNOWLEDGE_REINDEX: Capability.ASSET_MANAGE,
    Action.SKILL_REGISTER: Capability.ASSET_MANAGE,
    Action.SKILL_PUBLISH: Capability.ASSET_MANAGE,
    Action.SKILL_EXECUTE: Capability.JOB_SUBMIT,
    Action.SKILL_REVOKE: Capability.ASSET_MANAGE,
    Action.SKILL_READ: Capability.ASSET_VIEW,
    Action.MEMORY_ADD: Capability.ASSET_MANAGE,
    Action.MEMORY_READ: Capability.ASSET_VIEW,
    Action.MEMORY_UPDATE: Capability.ASSET_MANAGE,
    Action.MEMORY_DELETE: Capability.ASSET_MANAGE,
    Action.MEMORY_CLEAR: Capability.ASSET_MANAGE,
    Action.JOB_SUBMIT: Capability.JOB_SUBMIT,
    Action.JOB_READ: Capability.JOB_VIEW,
    Action.JOB_CANCEL: Capability.JOB_MANAGE,
    Action.JOB_RETRY: Capability.JOB_MANAGE,
    Action.MODEL_READ: Capability.MODEL_VIEW,
    Action.MODEL_CONFIGURE: Capability.MODEL_CONFIGURE,
    Action.MODEL_USE: Capability.MODEL_VIEW,
    Action.SECRET_USE: Capability.ASSET_MANAGE,
    Action.SECRET_ROTATE: Capability.ASSET_MANAGE,
    Action.OPERATION_REQUEST: Capability.OPERATION_REQUEST,
    Action.OPERATION_APPROVE: Capability.OPERATION_APPROVE,
    Action.CONFIG_READ: Capability.CONFIG_VIEW,
    Action.CONFIG_WRITE: Capability.CONFIG_WRITE,
    Action.CONFIG_ACTIVATE: Capability.CONFIG_ACTIVATE,
    Action.AUDIT_READ: Capability.AUDIT_VIEW,
    Action.TENANT_CREATE: Capability.TENANT_CREATE,
    Action.TENANT_MANAGE: Capability.TENANT_MANAGE,
    Action.OBS_VIEW: Capability.OBS_VIEW,
    Action.SEARCH_GLOBAL: Capability.SEARCH_GLOBAL,
}

ALL_CAPABILITIES = [c.value for c in Capability]

TENANT_ADMIN_CAPABILITIES = [
    Capability.TENANT_MANAGE.value, Capability.TENANT_VIEW.value,
    Capability.ASSET_MANAGE.value, Capability.ASSET_VIEW.value,
    Capability.JOB_SUBMIT.value, Capability.JOB_MANAGE.value, Capability.JOB_VIEW.value,
    Capability.MODEL_CONFIGURE.value, Capability.MODEL_VIEW.value,
    Capability.CONFIG_WRITE.value, Capability.CONFIG_ACTIVATE.value, Capability.CONFIG_VIEW.value,
    Capability.OPERATION_REQUEST.value, Capability.OPERATION_APPROVE.value, Capability.OPERATION_VIEW.value,
    Capability.OBS_VIEW.value, Capability.AUDIT_VIEW.value,
    Capability.SEARCH_GLOBAL.value, Capability.STEWARD_CHAT.value,
]

AGENT_CAPABILITIES = [
    Capability.ASSET_VIEW.value, Capability.JOB_SUBMIT.value, Capability.JOB_VIEW.value,
    Capability.MODEL_VIEW.value, Capability.CONFIG_VIEW.value,
    Capability.SEARCH_GLOBAL.value,
]

VIEWER_CAPABILITIES = [
    Capability.TENANT_VIEW.value, Capability.ASSET_VIEW.value, Capability.JOB_VIEW.value,
    Capability.MODEL_VIEW.value, Capability.CONFIG_VIEW.value, Capability.OPERATION_VIEW.value,
    Capability.OBS_VIEW.value, Capability.AUDIT_VIEW.value, Capability.SEARCH_GLOBAL.value,
]

MEETING_USER_CAPABILITIES = [
    Capability.ASSET_MANAGE.value, Capability.ASSET_VIEW.value,
    Capability.JOB_SUBMIT.value, Capability.JOB_VIEW.value,
    Capability.MODEL_VIEW.value,
    Capability.SEARCH_GLOBAL.value,
]


def capabilities_for_role(role: str) -> list[str]:
    if role == "platform_admin":
        return ALL_CAPABILITIES
    if role == "tenant_admin":
        return TENANT_ADMIN_CAPABILITIES
    if role == "agent":
        return AGENT_CAPABILITIES
    if role == "meeting_user":
        return MEETING_USER_CAPABILITIES
    if role == "viewer":
        return VIEWER_CAPABILITIES
    return VIEWER_CAPABILITIES


def actions_for_roles(roles: list[str]) -> list[str]:
    caps = set()
    for role in roles:
        caps.update(capabilities_for_role(role))
    actions = []
    for action, cap in ACTION_TO_CAPABILITY.items():
        if cap.value in caps:
            actions.append(action.value)
    return actions
