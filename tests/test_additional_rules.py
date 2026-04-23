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
            branches=["payment_credit_card", "payment_paypal", "payment_bank_transfer"],
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

    # First field should remain enabled
    assert result["payment_credit_card"].enabled is True
    # Second field should be disabled by one_of rule
    assert result["payment_paypal"].enabled is False
    # Third field should remain enabled (since it has no value)
    assert result["payment_bank_transfer"].enabled is True


def test_any_of_rule_evaluation() -> None:
    """Test that any_of rules work (though they don't directly affect field availability)."""
    fields = {
        "email": FieldDef(required=True),
        "phone": FieldDef(required=False),
        "address": FieldDef(required=False),
    }

    # Create some individual rules
    phone_required = requires("phone", when=lambda values, conditions: True)
    address_required = requires("address", when=lambda values, conditions: True)

    rules = [any_of([phone_required, address_required])]

    u = umpire(fields, rules)

    # Test - any_of doesn't directly affect field availability in our simple implementation
    result = u.check({"email": "test@example.com", "phone": "123-456-7890"})

    # Fields should be available as normal
    assert "email" in result
    assert "phone" in result
    assert "address" in result
