"""pyarrow → Iceberg Schema 转换（分配顺序 field-id）。

pyiceberg 的 ``pyarrow_to_schema`` 要求 parquet 已带 field-id，新建表时不适用。
本转换器按字段顺序分配 id 1..N，覆盖 MVP 常见类型。
"""
from __future__ import annotations

import pyarrow as pa
from pyiceberg.schema import Schema
from pyiceberg.types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    ListType,
    LongType,
    NestedField,
    StringType,
    StructType,
    TimestampType,
    TimestamptzType,
)

__all__ = ["arrow_to_iceberg_schema"]

_id = 0


def _next_id() -> int:
    global _id
    _id += 1
    return _id


def _convert_type(t: pa.DataType):
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
        if t.tz:
            return TimestamptzType()
        return TimestampType()
    if pa.types.is_list(t) or pa.types.is_large_list(t):
        return ListType(element_id=_next_id(), element=_convert_type(t.value_type), element_required=False)
    if pa.types.is_struct(t):
        fields = []
        for f in t:
            fields.append(NestedField(_next_id(), f.name, _convert_type(f.type), required=False))
        return StructType(*fields)
    raise ValueError(f"unsupported pyarrow type: {t}")


def arrow_to_iceberg_schema(arrow_schema: pa.Schema) -> Schema:
    global _id
    _id = 0
    fields = []
    for f in arrow_schema:
        fields.append(NestedField(_next_id(), f.name, _convert_type(f.type), required=False))
    return Schema(*fields)
