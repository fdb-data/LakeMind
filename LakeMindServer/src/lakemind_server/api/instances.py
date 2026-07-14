from __future__ import annotations
from fastapi import APIRouter, Request
from ..services.instance_registry import InstanceRegistry

router = APIRouter()


@router.get("")
async def list_instances(request: Request):
    service_type = request.query_params.get("service_type")
    return InstanceRegistry.list_instances(service_type)


@router.get("/{instance_id}")
async def get_instance(instance_id: str):
    return InstanceRegistry.get_instance(instance_id)
