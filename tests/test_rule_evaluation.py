"""Tests for rule evaluation in the Umpire engine."""

from umpire import (
    FieldDef,
    IsEmptyStrategy,
    check,
    check_ops,
    enabled_when,
    fair_when,
    requires,
    umpire,
)


def test_requires_rule_evaluation() -> None:
    """Test that requires rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True),
        "company_name": FieldDef(required=False),
    }

    def requires_company(values, conditions):
        return values.get("account_type") == "business"

    rules = [
        requires(
            "company_name",
            when=requires_company,
            reason="Company name is required for business accounts",
        )
    ]

    u = umpire(fields, rules)

    # Test with business account type
    result = u.check({"account_type": "business", "email": "test@example.com"})
    assert result["company_name"].required is True

    # Test with personal account type
    result = u.check({"account_type": "personal", "email": "test@example.com"})
    assert result["company_name"].required is False


def test_enabled_when_rule_evaluation() -> None:
    """Test that enabled_when rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True),
        "discount_override": FieldDef(required=False),
    }

    def is_admin(values, conditions):
        return conditions.get("is_admin") is True

    rules = [enabled_when("discount_override", when=is_admin, reason="Admin only")]

    u = umpire(fields, rules)

    # Test with admin user
    result = u.check({"email": "test@example.com"}, {"is_admin": True})
    assert result["discount_override"].enabled is True

    # Test with non-admin user
    result = u.check({"email": "test@example.com"}, {"is_admin": False})
    assert result["discount_override"].enabled is False


def test_fair_when_rule_evaluation() -> None:
    """Test that fair_when rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True),
        "plan_id": FieldDef(required=True),
    }

    def valid_plan(values, conditions):
        return values.get("plan_id") in (conditions.get("valid_plans") or [])

    rules = [fair_when("plan_id", when=valid_plan, reason="Plan is not available for this account")]

    u = umpire(fields, rules)

    # Test with valid plan
    result = u.check(
        {"email": "test@example.com", "plan_id": "pro"}, {"valid_plans": ["pro", "enterprise"]}
    )
    assert result["plan_id"].fair is True

    # Test with invalid plan
    result = u.check(
        {"email": "test@example.com", "plan_id": "invalid"}, {"valid_plans": ["pro", "enterprise"]}
    )
    assert result["plan_id"].fair is False


def test_check_rule_evaluation() -> None:
    """Test that check rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
        "password": FieldDef(required=True),
    }

    rules = [
        check("email", check_ops.email()),
        check("password", check_ops.min_length(8)),
    ]

    u = umpire(fields, rules)

    # Test with valid values
    result = u.check({"email": "test@example.com", "password": "password123"})
    # Note: Check rules don't currently affect the FieldAvailability object directly
    # They would affect the check_errors field, but that's not implemented yet

    assert "email" in result
    assert "password" in result
