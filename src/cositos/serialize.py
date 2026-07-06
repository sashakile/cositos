"""Widget-state serialization foundation: named types + the base64 buffer codec.

This module holds the boundary types whose round-trip is a checkable law and the pure
codec that converts the binary ``buffers`` produced by :func:`cositos.buffers.remove_buffers`
into the JSON ``buffers`` array of the ipywidgets **Widget State JSON schema v2**
(``application/vnd.jupyter.widget-state+json``), and back.

Buffers are handled by their *raw bytes*: a typed ``memoryview`` (e.g. ``float32``) does
not equal a plain-bytes ``memoryview`` with identical bytes, so everything is cast to a
flat byte view before encoding — matching ipywidgets ``_buffer_list_equal``.
"""

from __future__ import annotations

import base64
from typing import Any, TypeAlias

#: A path to a binary value inside state: dict keys (str) and/or list indices (int).
BufferPath: TypeAlias = list[Any]

#: One in-memory model: its comm id (``model_id``) and its full state dict.
ModelEntry: TypeAlias = tuple[str, dict[str, Any]]

#: The v2 Widget State JSON envelope: ``{version_major, version_minor, state}``.
Document: TypeAlias = dict[str, Any]

#: The output of :func:`cositos.buffers.remove_buffers`: stripped state + parallel
#: ``buffer_paths`` and binary ``buffers``.
SplitState: TypeAlias = tuple[Any, list[BufferPath], list[Any]]

#: A JSON-safe split: stripped state + the v2 ``buffers`` array (base64 records).
JsonSplit: TypeAlias = tuple[Any, list[dict[str, Any]]]


def encode_buffers_base64(split: SplitState) -> JsonSplit:
    """Encode a :data:`SplitState` into a JSON-safe :data:`JsonSplit`.

    The stripped state passes through unchanged; each binary buffer becomes a v2 record
    ``{"path": <path>, "encoding": "base64", "data": <b64 str>}``.
    """
    stripped, buffer_paths, buffers = split
    entries = [
        {"path": path, "encoding": "base64", "data": _b64encode(buf)}
        for path, buf in zip(buffer_paths, buffers, strict=True)
    ]
    return stripped, entries


def decode_buffers_base64(json_split: JsonSplit) -> SplitState:
    """Inverse of :func:`encode_buffers_base64`; buffers are returned as ``bytes``."""
    stripped, entries = json_split
    buffer_paths: list[BufferPath] = []
    buffers: list[Any] = []
    for entry in entries:
        buffer_paths.append(entry["path"])
        buffers.append(_b64decode(entry))
    return stripped, buffer_paths, buffers


def _b64encode(buf: Any) -> str:
    return base64.b64encode(_as_bytes(buf)).decode("ascii")


def _b64decode(entry: dict[str, Any]) -> bytes:
    encoding = entry.get("encoding")
    if encoding != "base64":
        raise ValueError(f"Unsupported buffer encoding: {encoding!r} (expected 'base64')")
    return base64.b64decode(entry["data"])


def _as_bytes(buf: Any) -> bytes:
    # Cast to a flat byte view so a typed memoryview serialises by its raw bytes.
    return memoryview(buf).cast("B").tobytes()
