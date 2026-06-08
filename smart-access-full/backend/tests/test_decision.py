"""
Tests for the core decision engine and scan API.
Run: pytest tests/ -v
"""

import pytest
from services.decision import DecisionEngine, DECISION_ALLOWED, DECISION_DENIED, DECISION_ALERT
from unittest.mock import MagicMock


@pytest.fixture
def engine():
    return DecisionEngine()


@pytest.fixture
def mock_employee():
    emp = MagicMock()
    emp.name = "Ahmed Khan"
    return emp


@pytest.fixture
def mock_visitor():
    vis = MagicMock()
    vis.name = "John Visitor"
    return vis


class TestDecisionEngine:

    def test_approved_vehicle_known_employee(self, engine, mock_employee):
        decision, reason = engine.decide("approved", mock_employee, None)
        assert decision == DECISION_ALLOWED
        assert "Ahmed Khan" in reason

    def test_approved_vehicle_known_visitor(self, engine, mock_visitor):
        decision, reason = engine.decide("approved", None, mock_visitor)
        assert decision == DECISION_ALLOWED
        assert "John Visitor" in reason

    def test_approved_vehicle_unknown_driver(self, engine):
        decision, reason = engine.decide("approved", None, None)
        assert decision == DECISION_ALERT
        assert "unrecognized" in reason.lower()

    def test_blacklisted_vehicle_always_denied(self, engine, mock_employee):
        # Even a known employee in a blacklisted car gets denied
        decision, reason = engine.decide("blacklisted", mock_employee, None)
        assert decision == DECISION_DENIED
        assert "blacklisted" in reason.lower()

    def test_unknown_vehicle_known_employee_gets_alert(self, engine, mock_employee):
        decision, reason = engine.decide("unknown", mock_employee, None)
        assert decision == DECISION_ALERT

    def test_unknown_vehicle_unknown_driver_denied(self, engine):
        decision, reason = engine.decide("unknown", None, None)
        assert decision == DECISION_DENIED

    def test_no_plate_detected(self, engine):
        decision, reason = engine.decide("unknown", None, None)
        assert decision == DECISION_DENIED

    def test_unknown_vehicle_visitor_denied(self, engine, mock_visitor):
        # Pre-approved visitor in an unregistered car = deny
        decision, reason = engine.decide("unknown", None, mock_visitor)
        assert decision == DECISION_DENIED
