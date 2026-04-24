"""Additional tests for missing rule types."""

from umpire import (
    FieldDef,
    any_of,
    disables,
    one_of,
    requires,
    umpire,
)


def test_disables_rule_evaluation() -> None:
    """Test that disables rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True),
        "discount_code": FieldDef(required=False),
        "custom_discount": FieldDef(required=False),
    }

    def has_discount_code(values, conditions):
        return values.get("discount_code") is not None

    rules = [
        disables(
            source="discount_code",
            targets=["custom_discount"],
            when=has_discount_code,
            reason="Cannot use both discount code and custom discount",
        )
    ]

    u = umpire(fields, rules)

    # Test with discount code present - custom_discount should be disabled
    result = u.check({"email": "test@example.com", "discount_code": "SAVE10"})

    assert result["email"].enabled is True
    assert result["discount_code"].enabled is True
    assert result["custom_discount"].enabled is False  # Should be disabled by rule


def test_one_of_rule_evaluation() -> None:
    """Test that one_of rules are evaluated correctly."""
    fields = {
        "email": FieldDef(required=True),
        "payment_credit_card": FieldDef(required=False),
        "payment_paypal": FieldDef(required=False),
        "payment_bank_transfer": FieldDef(required=False),
    }

    rules = [
        one_of(
            group="payment_method",
            branches={
                "card": ["payment_credit_card"],
                "paypal": ["payment_paypal"],
                "bank": ["payment_bank_transfer"],
            },
            reason="Only one payment method can be selected",
        )
    ]

    u = umpire(fields, rules)

    # Test with multiple payment methods - only first should be enabled
    result = u.check(
        {
            "email": "test@example.com",
            "payment_credit_card": "1234",
            "payment_paypal": "paypal@example.com",
        }
    )

    assert result["payment_credit_card"].enabled is True
    assert result["payment_paypal"].enabled is False
    assert result["payment_bank_transfer"].enabled is False


def test_one_of_uses_previous_state_to_resolve_new_active_branch() -> None:
    """When a new branch becomes satisfied, previous state should break ties."""
    fields = {
        "payment_credit_card": FieldDef(),
        "payment_paypal": FieldDef(),
    }

    rules = [
        one_of(
            group="payment_method",
            branches={
                "card": ["payment_credit_card"],
                "paypal": ["payment_paypal"],
            },
        )
    ]

    u = umpire(fields, rules)

    before_values = {"payment_credit_card": "1234"}
    after_values = {"payment_credit_card": "1234", "payment_paypal": "paypal@example.com"}
    result = u.check(after_values, previous_values=before_values)

    assert result["payment_credit_card"].enabled is False
    assert result["payment_paypal"].enabled is True


def test_any_of_rule_evaluation() -> None:
    """any_of implements OR semantics across compatible inner rules."""
    fields = {
        "email": FieldDef(required=True),
        "phone": FieldDef(required=False),
    }

    phone_allowed_by_email = requires("phone", dependency="email")
    phone_allowed_by_admin = requires(
        "phone", when=lambda values, conditions: conditions["is_admin"]
    )

    rules = [any_of([phone_allowed_by_email, phone_allowed_by_admin])]

    u = umpire(fields, rules)

    result = u.check({}, {"is_admin": False})
    assert result["phone"].enabled is False

    result = u.check({}, {"is_admin": True})
    assert result["phone"].enabled is True

    result = u.check({"email": "test@example.com"}, {"is_admin": False})
    assert result["phone"].enabled is True
