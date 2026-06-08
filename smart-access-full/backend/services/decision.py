from models.models import Employee, Visitor


DECISION_ALLOWED = "allowed"
DECISION_DENIED = "denied"
DECISION_ALERT = "allowed_with_alert"


class DecisionEngine:
    """
    Core access control logic.
    Returns (decision, reason) tuple.

    Rules:
        IF vehicle approved AND driver is known employee  → ALLOW
        IF vehicle approved AND driver is pre-approved visitor → ALLOW
        IF vehicle approved AND driver is unknown  → ALLOW WITH ALERT
        IF vehicle unknown AND driver is known employee  → ALLOW WITH ALERT
        IF vehicle blacklisted  → DENY always
        IF vehicle unknown AND driver unknown  → DENY
        IF no plate detected  → DENY
    """

    def decide(
        self,
        vehicle_status: str,           # approved | blacklisted | unknown
        driver_employee: Employee | None,
        driver_visitor: Visitor | None,
    ) -> tuple[str, str]:

        driver_known = driver_employee is not None or driver_visitor is not None
        driver_label = (
            driver_employee.name if driver_employee
            else driver_visitor.name if driver_visitor
            else "unknown driver"
        )

        # Hard deny — blacklisted vehicle, no exceptions
        if vehicle_status == "blacklisted":
            return DECISION_DENIED, f"Vehicle is blacklisted. {driver_label} denied entry."

        # No plate detected at all
        if vehicle_status == "unknown" and not driver_known:
            return DECISION_DENIED, "Unrecognized vehicle and unknown driver."

        # Approved vehicle
        if vehicle_status == "approved":
            if driver_employee:
                return DECISION_ALLOWED, f"Approved vehicle. Driver: {driver_employee.name} (employee)."
            if driver_visitor:
                return DECISION_ALLOWED, f"Approved vehicle. Driver: {driver_visitor.name} (pre-approved visitor)."
            # Approved vehicle but unknown driver
            return DECISION_ALERT, "Approved vehicle but driver is unrecognized. Security notified."

        # Unknown vehicle but known employee driving
        if vehicle_status == "unknown" and driver_employee:
            return DECISION_ALERT, f"Unknown vehicle driven by employee {driver_employee.name}. Security notified."

        # Unknown vehicle with known visitor
        if vehicle_status == "unknown" and driver_visitor:
            return DECISION_DENIED, f"Pre-approved visitor {driver_visitor.name} in unregistered vehicle. Denied."

        # Fallback
        return DECISION_DENIED, "Access denied. Could not verify vehicle or driver."
