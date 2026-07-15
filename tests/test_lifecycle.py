"""Tests for the pure widget lifecycle reducer — no kernel, no transport, no mocking.

Loads fixtures from ``fixtures/lifecycle/*.json`` and calls ``reduce`` directly,
asserting the exact output. Also tests edge cases that cannot be expressed in JSON
(cycles, identity fields, error transitions).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cositos.lifecycle import (
    ApplyState,
    Close,
    CommIdAssigned,
    Error,
    Inbound,
    InvokeCustom,
    Listen,
    Open,
    Phase,
    Send,
    SendCustom,
    SendState,
    TransportCapabilities,
    reduce,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "lifecycle"


def load_fixture(name: str) -> list:
    with open(FIXTURES / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixture-driven tests (cross-language contract)
# ---------------------------------------------------------------------------

def _event_from_fixture(event: dict):
    """Convert a fixture event dict to a lifecycle event instance."""
    kind = event["kind"]
    if kind == "open":
        return Open()
    elif kind == "send_state":
        return SendState(include=event.get("include"))
    elif kind == "send_custom":
        return SendCustom(content=event.get("content"), buffers=event.get("buffers", []))
    elif kind == "inbound":
        return Inbound(message=event["message"])
    elif kind == "close":
        return Close()
    elif kind == "comm_id_assigned":
        return CommIdAssigned(id=event["id"])
    else:
        raise ValueError(f"unknown event kind: {kind}")


def _capabilities_from_fixture(case: list) -> TransportCapabilities:
    """Extract capabilities from a fixture case (optional 6th element)."""
    if len(case) >= 6 and isinstance(case[5], dict):
        return TransportCapabilities(**case[5])
    return TransportCapabilities()


def _effect_matches_fixture(effect, expected: dict) -> bool:
    """Check that an effect matches the fixture's condensed representation."""
    if isinstance(effect, Send):
        return expected.get("kind") == "send" and expected.get("msg_type") == effect.msg_type
    elif isinstance(effect, Listen):
        return expected.get("kind") == "listen"
    elif isinstance(effect, ApplyState):
        return expected.get("kind") == "apply_state"
    elif isinstance(effect, InvokeCustom):
        return expected.get("kind") == "invoke_custom"
    elif isinstance(effect, Error):
        return expected.get("kind") == "error"
    return False


@pytest.mark.parametrize("fixture_file", sorted(os.listdir(FIXTURES)))
def test_against_fixture(fixture_file: str):
    """Load a fixture and assert that reduce produces the expected output."""
    fixture = load_fixture(fixture_file)
    for case in fixture:
        phase_in = Phase(case[0])
        event = _event_from_fixture(case[1])
        state_in = case[2]
        phase_out = Phase(case[3])
        expected_effects = case[4]

        phase, effects = reduce(phase_in, event, state_in, _capabilities_from_fixture(case))

        assert phase == phase_out, f"expected phase {phase_out}, got {phase}"
        assert len(effects) == len(expected_effects), (
            f"expected {len(expected_effects)} effects, got {len(effects)}: {effects}"
        )
        for effect, expected in zip(effects, expected_effects):
            assert _effect_matches_fixture(effect, expected), (
                f"effect mismatch: {effect} vs {expected}"
            )


# ---------------------------------------------------------------------------
# Behavioral tests (edge cases not expressible in JSON fixtures)
# ---------------------------------------------------------------------------

def test_open_from_unopened_produces_comm_open():
    phase, effects = reduce(Phase.UNOPENED, Open(), {"value": 0}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 2
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_open"
    assert isinstance(effects[1], Listen)


def test_open_from_open_is_idempotent():
    phase, effects = reduce(Phase.OPEN, Open(), {"value": 0}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert effects == []


def test_open_from_closed_reopens():
    phase, effects = reduce(Phase.CLOSED, Open(), {"value": 0}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 2
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_open"


def test_one_way_open_no_listen():
    caps = TransportCapabilities(supports_receive=False)
    phase, effects = reduce(Phase.UNOPENED, Open(), {"value": 0}, caps)
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_open"


def test_full_send_state_includes_identity():
    state = {"_esm": "e", "value": 5}
    phase, effects = reduce(Phase.OPEN, SendState(), state, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 1
    send = effects[0]
    assert isinstance(send, Send)
    assert send.msg_type == "comm_msg"
    # Data should include identity fields
    data = send.data
    assert data["method"] == "update"
    assert "_model_module" in data["state"]
    assert "_view_name" in data["state"]
    assert "value" in data["state"]


def test_filtered_send_state_omits_identity():
    state = {"_esm": "e", "value": 5, "other": 1}
    phase, effects = reduce(Phase.OPEN, SendState(include={"value"}), state, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 1
    send = effects[0]
    assert isinstance(send, Send)
    assert send.msg_type == "comm_msg"
    data = send.data
    keys = set(data["state"].keys())
    assert keys == {"value"}
    assert "_model_module" not in keys


def test_send_state_from_unopened_errors():
    phase, effects = reduce(Phase.UNOPENED, SendState(), {}, TransportCapabilities())
    assert phase == Phase.UNOPENED
    assert len(effects) == 1
    assert isinstance(effects[0], Error)
    assert "open comm" in effects[0].message.lower()


def test_send_custom_from_open():
    phase, effects = reduce(
        Phase.OPEN, SendCustom(content={"event": "click"}), {}, TransportCapabilities()
    )
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_msg"


def test_send_custom_without_support_errors():
    caps = TransportCapabilities(supports_custom=False)
    phase, effects = reduce(
        Phase.OPEN, SendCustom(content={"event": "click"}), {}, caps
    )
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], Error)


def test_close_from_open():
    phase, effects = reduce(Phase.OPEN, Close(), {}, TransportCapabilities())
    assert phase == Phase.CLOSED
    assert len(effects) == 1
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_close"


def test_close_from_unopened_is_noop():
    phase, effects = reduce(Phase.UNOPENED, Close(), {}, TransportCapabilities())
    assert phase == Phase.UNOPENED
    assert effects == []


def test_close_from_closed_is_noop():
    phase, effects = reduce(Phase.CLOSED, Close(), {}, TransportCapabilities())
    assert phase == Phase.CLOSED
    assert effects == []


def test_comm_id_assigned():
    phase, effects = reduce(Phase.OPEN, CommIdAssigned(id="abc-123"), {}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert effects == []  # shell stores the id, reducer doesn't produce effects


def test_inbound_update_produces_apply_state():
    message = {"method": "update", "state": {"value": 42}, "buffer_paths": []}
    phase, effects = reduce(Phase.OPEN, Inbound(message=message), {}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], ApplyState)
    assert effects[0].state == {"value": 42}


def test_inbound_request_state_without_support_is_silent():
    message = {"method": "request_state"}
    caps = TransportCapabilities(supports_request_state=False)
    phase, effects = reduce(Phase.OPEN, Inbound(message=message), {"_esm": "e", "value": 5}, caps)
    assert phase == Phase.OPEN
    assert effects == []


def test_inbound_request_state_produces_send():
    message = {"method": "request_state"}
    state = {"_esm": "e", "value": 5}
    phase, effects = reduce(Phase.OPEN, Inbound(message=message), state, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], Send)
    assert effects[0].msg_type == "comm_msg"


def test_inbound_custom_produces_invoke_custom():
    message = {"method": "custom", "content": {"event": "click"}}
    phase, effects = reduce(Phase.OPEN, Inbound(message=message), {}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert len(effects) == 1
    assert isinstance(effects[0], InvokeCustom)


def test_inbound_unknown_is_ignored():
    message = {"method": "bogus"}
    phase, effects = reduce(Phase.OPEN, Inbound(message=message), {}, TransportCapabilities())
    assert phase == Phase.OPEN
    assert effects == []


def test_inbound_from_unopened_is_buffered():
    message = {"method": "update", "state": {"value": 42}, "buffer_paths": []}
    phase, effects = reduce(Phase.UNOPENED, Inbound(message=message), {}, TransportCapabilities())
    assert phase == Phase.UNOPENED
    assert effects == []


def test_inbound_from_closed_is_dropped():
    message = {"method": "update", "state": {"value": 42}, "buffer_paths": []}
    phase, effects = reduce(Phase.CLOSED, Inbound(message=message), {}, TransportCapabilities())
    assert phase == Phase.CLOSED
    assert effects == []


def test_reduce_is_pure():
    """Same inputs produce same outputs every time."""
    phase, events = reduce(Phase.UNOPENED, Open(), {"value": 0}, TransportCapabilities())
    phase2, events2 = reduce(Phase.UNOPENED, Open(), {"value": 0}, TransportCapabilities())
    assert phase == phase2
    assert len(events) == len(events2)