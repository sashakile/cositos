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
from collections.abc import Iterable
from typing import Any, TypeAlias

from cositos.buffers import put_buffers, remove_buffers
from cositos.protocol import ANYWIDGET_MODULE_VERSION

#: Widget State JSON schema version (distinct from the protocol version 2.1.0).
STATE_VERSION_MAJOR = 2
STATE_VERSION_MINOR = 0

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

#: One model's serialized record in the v2 ``state`` map (keyed by ``model_id``).
Record: TypeAlias = dict[str, Any]


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


def dump_model(
    entry: ModelEntry, *, anywidget_version: str = ANYWIDGET_MODULE_VERSION
) -> tuple[str, Record]:
    """Serialize one :data:`ModelEntry` to ``(model_id, record)`` per schema v2.

    The anywidget identity (``model_name``/``model_module``/``model_module_version``) is
    read from ``state`` if the host set the ``_model_*`` fields, else defaulted to the
    ``AnyModel``/``anywidget`` frontend. ``state`` itself is preserved verbatim (minus
    binary values, which move to ``buffers``), so :func:`load_model` is its exact inverse.
    """
    model_id, state = entry
    stripped, buffer_paths, buffers = remove_buffers(state)
    _, entries = encode_buffers_base64((stripped, buffer_paths, buffers))
    record: Record = {
        "model_name": state.get("_model_name", "AnyModel"),
        "model_module": state.get("_model_module", "anywidget"),
        "model_module_version": state.get("_model_module_version", anywidget_version),
        "state": stripped,
    }
    if entries:
        record["buffers"] = entries
    return model_id, record


def load_model(item: tuple[str, Record]) -> ModelEntry:
    """Inverse of :func:`dump_model`: rebuild ``(model_id, state)`` from a record.

    Binary buffers are decoded and merged back into ``state`` in place; the returned
    ``state`` carries real ``bytes`` at the buffer paths.
    """
    model_id, record = item
    state = record["state"]
    _, buffer_paths, buffers = decode_buffers_base64((state, record.get("buffers", [])))
    put_buffers(state, buffer_paths, buffers)
    return model_id, state


def dump_document(
    entries: Iterable[ModelEntry], *, anywidget_version: str = ANYWIDGET_MODULE_VERSION
) -> Document:
    """Serialize many :data:`ModelEntry` values into a v2 Widget State document.

    The envelope is ``{version_major, version_minor, state}`` where ``state`` maps each
    ``model_id`` to its record. A composed UI needs nothing special: children are stored
    as ``"IPY_MODEL_<id>"`` strings in ordinary state and round-trip verbatim.
    """
    state = dict(dump_model(entry, anywidget_version=anywidget_version) for entry in entries)
    return {
        "version_major": STATE_VERSION_MAJOR,
        "version_minor": STATE_VERSION_MINOR,
        "state": state,
    }


def load_document(doc: Document) -> list[ModelEntry]:
    """Inverse of :func:`dump_document`: rebuild the list of ``(model_id, state)``.

    References between models are plain ``"IPY_MODEL_<id>"`` strings, so loading is a flat
    id-keyed pass — reference cycles are safe (no recursive inlining).
    """
    return [load_model(item) for item in doc["state"].items()]
