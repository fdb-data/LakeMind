from __future__ import annotations
import pytest
from lakemind_server.services.job_state_machine import (
    can_transition, transition, is_terminal, VALID_TRANSITIONS
)


class TestJobStateMachine:
    def test_submitted_to_queued(self):
        assert can_transition("SUBMITTED", "QUEUED")

    def test_queued_to_running(self):
        assert can_transition("QUEUED", "RUNNING")

    def test_running_to_succeeded(self):
        assert can_transition("RUNNING", "SUCCEEDED")

    def test_running_to_failed(self):
        assert can_transition("RUNNING", "FAILED")

    def test_running_to_cancelling(self):
        assert can_transition("RUNNING", "CANCELLING")

    def test_cancelling_to_cancelled(self):
        assert can_transition("CANCELLING", "CANCELLED")

    def test_running_to_lost(self):
        assert can_transition("RUNNING", "LOST")

    def test_queued_to_timed_out(self):
        assert can_transition("QUEUED", "TIMED_OUT")

    def test_invalid_succeeded_to_running(self):
        assert not can_transition("SUCCEEDED", "RUNNING")

    def test_invalid_failed_to_queued(self):
        assert not can_transition("FAILED", "QUEUED")

    def test_transition_returns_target(self):
        assert transition("SUBMITTED", "QUEUED") == "QUEUED"

    def test_transition_invalid_raises(self):
        with pytest.raises(ValueError, match="INVALID_TRANSITION"):
            transition("SUCCEEDED", "RUNNING")

    def test_terminal_states(self):
        assert is_terminal("SUCCEEDED")
        assert is_terminal("FAILED")
        assert is_terminal("TIMED_OUT")
        assert is_terminal("CANCELLED")
        assert is_terminal("LOST")

    def test_non_terminal_states(self):
        assert not is_terminal("SUBMITTED")
        assert not is_terminal("QUEUED")
        assert not is_terminal("RUNNING")
        assert not is_terminal("CANCELLING")

    def test_terminal_has_no_outgoing(self):
        for state in ["SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "LOST"]:
            assert len(VALID_TRANSITIONS[state]) == 0
