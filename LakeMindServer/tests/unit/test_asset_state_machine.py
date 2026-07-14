from __future__ import annotations
import pytest
from lakemind_server.services.asset_state_machine import (
    can_transition, transition, check_ready, check_degraded
)


class TestAssetStateMachine:
    def test_draft_to_creating(self):
        assert can_transition("DRAFT", "CREATING")

    def test_creating_to_processing(self):
        assert can_transition("CREATING", "PROCESSING")

    def test_processing_to_ready(self):
        assert can_transition("PROCESSING", "READY")

    def test_processing_to_degraded(self):
        assert can_transition("PROCESSING", "DEGRADED")

    def test_ready_to_deleting(self):
        assert can_transition("READY", "DELETING")

    def test_deleting_to_deleted(self):
        assert can_transition("DELETING", "DELETED")

    def test_invalid_ready_to_creating(self):
        assert not can_transition("READY", "CREATING")

    def test_deleted_has_no_outgoing(self):
        assert not can_transition("DELETED", "DRAFT")

    def test_transition_returns_target(self):
        assert transition("DRAFT", "CREATING") == "CREATING"

    def test_transition_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid state transition"):
            transition("DELETED", "DRAFT")

    def test_check_ready_all_required_ready(self):
        bindings = [
            {"is_required": True, "status": "READY"},
            {"is_required": True, "status": "READY"},
        ]
        assert check_ready(bindings)

    def test_check_ready_missing_required(self):
        bindings = [
            {"is_required": True, "status": "READY"},
            {"is_required": True, "status": "FAILED"},
        ]
        assert not check_ready(bindings)

    def test_check_degraded_optional_failed(self):
        bindings = [
            {"is_required": True, "status": "READY"},
            {"is_required": False, "status": "FAILED"},
        ]
        assert check_degraded(bindings)

    def test_check_degraded_required_failed(self):
        bindings = [
            {"is_required": True, "status": "FAILED"},
            {"is_required": False, "status": "READY"},
        ]
        assert not check_degraded(bindings)
