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

    result = u.check({"email": "test@example.com", "password": "password123"})
    assert result["email"].check_errors == ()
    assert result["password"].check_errors == ()

    result = u.check({"email": "not-an-email", "password": "short"})
    assert len(result["email"].check_errors) == 1
    assert result["email"].check_errors[0].field == "email"
    assert "email" in result["email"].check_errors[0].reason.lower()
    assert len(result["password"].check_errors) == 1
    assert result["password"].check_errors[0].field == "password"


def test_disabled_required_field_reports_not_required() -> None:
    """Disabled fields should not also be reported as required."""
    fields = {
        "has_coupon": FieldDef(),
        "coupon_code": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    }

    rules = [enabled_when("coupon_code", lambda values, conditions: False)]

    u = umpire(fields, rules)

    result = u.check({})

    assert result["coupon_code"].enabled is False
    assert result["coupon_code"].required is False


def test_requires_dependency_uses_dependency_satisfaction_and_availability() -> None:
    """Dependency-backed requires mirrors Umpire's dependency semantics."""
    fields = {
        "password": FieldDef(is_empty=IsEmptyStrategy.STRING),
        "confirm_password": FieldDef(is_empty=IsEmptyStrategy.STRING),
    }

    rules = [requires("confirm_password", dependency="password")]

    u = umpire(fields, rules)

    assert u.check({})["confirm_password"].enabled is False
    assert u.check({"password": ""})["confirm_password"].enabled is False
    assert u.check({"password": "hunter2"})["confirm_password"].enabled is True


def test_requires_dependency_respects_dependency_availability() -> None:
    """A dependency must be enabled and fair before its dependent can be enabled."""
    fields = {
        "password": FieldDef(is_empty=IsEmptyStrategy.STRING),
        "confirm_password": FieldDef(is_empty=IsEmptyStrategy.STRING),
    }

    rules = [
        enabled_when("password", lambda values, conditions: False),
        requires("confirm_password", dependency="password"),
    ]

    u = umpire(fields, rules)

    result = u.check({"password": "hunter2"})

    assert result["password"].enabled is False
    assert result["confirm_password"].enabled is False


def test_email_check_operation() -> None:
    """Test email check operation."""
    email_check = check_ops.email()

    # Test valid email
    result = email_check("test@example.com", "email")
    assert result is None  # No error for valid email

    # Test invalid email
    result = email_check("invalid-email", "email")
    assert result is not None
    assert result.field == "email"
    assert "email" in result.reason.lower()

    # Test non-string input
    result = email_check(123, "email")
    assert result is not None
    assert result.field == "email"
    assert "string" in result.reason.lower()


def test_min_length_check_operation() -> None:
    """Test min_length check operation."""
    min_length_check = check_ops.min_length(8)

    # Test valid length
    result = min_length_check("password123", "password")
    assert result is None  # No error for valid length

    # Test invalid length
    result = min_length_check("short", "password")
    assert result is not None
    assert result.field == "password"
    assert "8" in result.reason

    # Test non-string input
    result = min_length_check(123, "password")
    assert result is not None
    assert result.field == "password"
    assert "string" in result.reason.lower()


def test_url_check_operation() -> None:
    """Test url check operation."""
    url_check = check_ops.url()

    # Test valid URL
    result = url_check("https://example.com", "website")
    assert result is None  # No error for valid URL

    # Test invalid URL
    result = url_check("not-a-url", "website")
    assert result is not None
    assert result.field == "website"
    assert "url" in result.reason.lower()

    # Test non-string input
    result = url_check(123, "website")
    assert result is not None
    assert result.field == "website"
    assert "string" in result.reason.lower()


def test_matches_check_operation() -> None:
    """Test matches check operation."""
    import re

    matches_check = check_ops.matches(r"^[A-Z][a-z]+$")

    # Test valid match
    result = matches_check("Hello", "name_field")
    assert result is None  # No error for valid match

    # Test invalid match
    result = matches_check("123invalid", "name_field")
    assert result is not None
    assert result.field == "name_field"
    assert "match" in result.reason.lower()

    # Test with compiled regex pattern
    compiled_pattern = re.compile(r"^\d+$")
    compiled_check = check_ops.matches(compiled_pattern)
    result = compiled_check("123", "number_field")
    assert result is None  # No error for valid match with compiled pattern

    result = compiled_check("abc", "number_field")
    assert result is not None  # Error for invalid match with compiled pattern
    assert result.field == "number_field"

    # Test non-string input
    result = matches_check(123, "name_field")
    assert result is not None
    assert result.field == "name_field"
    assert "string" in result.reason.lower()


def test_integer_check_operation() -> None:
    """Test integer check operation."""
    integer_check = check_ops.integer()

    # Test valid integer
    result = integer_check(123, "number_field")
    assert result is None  # No error for valid integer

    # Test invalid integer (float)
    result = integer_check(12.34, "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "integer" in result.reason.lower()


def test_max_length_check_operation() -> None:
    """Test max_length check operation."""
    max_length_check = check_ops.max_length(10)

    # Test valid length
    result = max_length_check("short", "text_field")
    assert result is None  # No error for valid length

    # Test invalid length
    result = max_length_check("this is too long", "text_field")
    assert result is not None
    assert result.field == "text_field"
    assert "10" in result.reason

    # Test non-string input
    result = max_length_check(123, "text_field")
    assert result is not None
    assert result.field == "text_field"
    assert "string" in result.reason.lower()


def test_min_value_check_operation() -> None:
    """Test min_value check operation."""
    min_value_check = check_ops.min_value(5)

    # Test valid value
    result = min_value_check(10, "number_field")
    assert result is None  # No error for valid value

    # Test invalid value
    result = min_value_check(3, "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "5" in result.reason

    # Test non-numeric input
    result = min_value_check("not a number", "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "number" in result.reason.lower()


def test_max_value_check_operation() -> None:
    """Test max_value check operation."""
    max_value_check = check_ops.max_value(100)

    # Test valid value
    result = max_value_check(50, "number_field")
    assert result is None  # No error for valid value

    # Test invalid value
    result = max_value_check(150, "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "100" in result.reason

    # Test non-numeric input
    result = max_value_check("not a number", "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "number" in result.reason.lower()


def test_range_value_check_operation() -> None:
    """Test range_value check operation."""
    range_check = check_ops.range_value(10, 100)

    # Test valid value within range
    result = range_check(50, "number_field")
    assert result is None  # No error for valid value

    # Test invalid value below range
    result = range_check(5, "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "10" in result.reason and "100" in result.reason

    # Test invalid value above range
    result = range_check(150, "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "10" in result.reason and "100" in result.reason

    # Test non-numeric input
    result = range_check("not a number", "number_field")
    assert result is not None
    assert result.field == "number_field"
    assert "number" in result.reason.lower()
