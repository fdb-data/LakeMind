from __future__ import annotations
from typing import Any
import pyarrow as pa

_id = 0

def _next_id() -> int:
    global _id
    _id += 1
    return _id

def _convert_type(t: pa.DataType):
    from pyiceberg.types import (
        StringType, BooleanType, IntegerType, LongType,
        FloatType, DoubleType, DateType, BinaryType,
        DecimalType, TimestampType, TimestamptzType,
        ListType, StructType, NestedField,
    )
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return StringType()
    if pa.types.is_boolean(t):
        return BooleanType()
    if pa.types.is_int32(t):
        return IntegerType()
    if pa.types.is_int64(t):
        return LongType()
    if pa.types.is_float32(t):
        return FloatType()
    if pa.types.is_float64(t):
        return DoubleType()
    if pa.types.is_date32(t) or pa.types.is_date64(t):
        return DateType()
    if pa.types.is_binary(t) or pa.types.is_large_binary(t):
        return BinaryType()
    if pa.types.is_decimal(t):
        return DecimalType(t.precision, t.scale)
    if pa.types.is_timestamp(t):
        if t.tz is not None:
            return TimestamptzType()
        return TimestampType()
    if pa.types.is_list(t) or pa.types.is_large_list(t):
        elem_type = _convert_type(t.value_type)
        return ListType(element_id=_next_id(), element=elem_type, element_required=False)
    if pa.types.is_struct(t):
        fields = []
        for i, f in enumerate(t):
            fields.append(NestedField(field_id=_next_id(), name=f.name,
                                      field_type=_convert_type(f.type), required=False))
        return StructType(*fields)
    raise ValueError(f"Unsupported type: {t}")

def arrow_to_iceberg_schema(arrow_schema: pa.Schema):
    from pyiceberg.schema import Schema
    global _id
    _id = 0
    from pyiceberg.types import NestedField
    fields = []
    for i, f in enumerate(arrow_schema):
        fields.append(NestedField(field_id=_next_id(), name=f.name,
                                  field_type=_convert_type(f.type), required=False))
    return Schema(*fields)
