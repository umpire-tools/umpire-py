"""Additional tests for missing rule types."""

from umpire import (
    FieldDef,
    any_of,
    disables,
    either_of,
    enabled_when,
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


def test_either_of_per_branch_evaluation() -> None:
    """Either_of evaluates branches holistically — a branch passes only when ALL its targets pass."""
    fields = {
        "email": FieldDef(required=False),
        "phone": FieldDef(required=False),
    }
    rules = [
        either_of("contact", {
            "branch_a": [
                enabled_when("email", when=lambda v, c: True),
                enabled_when("phone", when=lambda v, c: False, reason="phone disabled in A"),
            ],
            "branch_b": [
                enabled_when("email", when=lambda v, c: False, reason="email disabled in B"),
                enabled_when("phone", when=lambda v, c: True),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com", "phone": "555"})

    # Both branches fail holistically (each has one disabled target).
    # No branch passes → combine failures per-target.
    # _combine_failures uses first snapshot's state as base:
    #   email: branch_a has it enabled → stays enabled, reasons from branch_b
    #   phone: branch_a has it disabled → stays disabled
    assert result["email"].enabled is True
    assert result["email"].reason == "email disabled in B"
    assert result["phone"].enabled is False
    assert result["phone"].reason == "phone disabled in A"


def test_either_of_all_branches_fail() -> None:
    """When all branches fail holistically, failures are combined per-target."""
    fields = {
        "email": FieldDef(required=False),
        "phone": FieldDef(required=False),
    }
    rules = [
        either_of("contact", {
            "branch_a": [
                enabled_when("email", when=lambda v, c: False, reason="bad email"),
                enabled_when("phone", when=lambda v, c: False, reason="bad phone"),
            ],
            "branch_b": [
                enabled_when("email", when=lambda v, c: False, reason="also bad email"),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com", "phone": "555"})
    assert result["email"].enabled is False
    assert result["phone"].enabled is False
    assert result["email"].reason == "bad email"
    assert "also bad email" in result["email"].reasons


def test_either_of_non_overlapping_targets() -> None:
    """Branches targeting non-overlapping field sets — verify no cross-contamination."""
    fields = {
        "email": FieldDef(required=False),
        "phone": FieldDef(required=False),
    }
    rules = [
        either_of("contact", {
            "email_branch": [
                enabled_when("email", when=lambda v, c: True),
            ],
            "phone_branch": [
                enabled_when("phone", when=lambda v, c: True),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com", "phone": "555"})
    assert result["email"].enabled is True
    assert result["phone"].enabled is True


def test_either_of_branch_zero_targets() -> None:
    """A branch with zero leaf targets passes trivially — its snapshot is applied wholesale."""
    fields = {
        "email": FieldDef(required=False),
    }
    empty_one_of_rule = one_of("empty_group", {})
    rules = [
        either_of("test", {
            "empty": [empty_one_of_rule],
            "fail": [
                enabled_when("email", when=lambda v, c: False, reason="disabled"),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com"})
    assert result["email"].enabled is True


def test_either_of_nested_one_of_targets() -> None:
    """Nested OneOf targets are collected correctly for branch evaluation."""
    fields = {
        "email": FieldDef(required=False),
        "phone": FieldDef(required=False),
    }

    inner_one_of = one_of("inner_group", {
        "a": ["email"],
        "b": ["phone"],
    })

    rules = [
        either_of("outer", {
            "branch_1": [
                enabled_when("email", when=lambda v, c: True),
                inner_one_of,
            ],
            "branch_2": [
                enabled_when("email", when=lambda v, c: False, reason="nope"),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com", "phone": "555"})

    # branch_1 targets: {email (from enabled_when), email, phone (from OneOf)} = {email, phone}
    # In branch_1 scratch: email is enabled (enabled_when True), but OneOf makes phone disabled
    # So branch_1 does NOT pass holistically (phone disabled)
    # branch_2: email disabled → fails
    # Both fail → _combine_failures uses first branch's state as base:
    #   email: branch_1 has it enabled → stays enabled, reason from branch_2
    #   phone: branch_1 has it disabled (OneOf) → stays disabled
    # The key assertion: if OneOf targets were NOT collected, phone would be enabled=True
    assert result["email"].enabled is True
    assert result["email"].reason == "nope"
    assert result["phone"].enabled is False


def test_either_of_overlapping_both_pass() -> None:
    """When multiple branches pass and target overlapping fields, first branch's full snapshot wins."""
    fields = {
        "email": FieldDef(required=False),
        "phone": FieldDef(required=False),
    }
    rules = [
        either_of("contact", {
            "email_first": [
                enabled_when("email", when=lambda v, c: True),
            ],
            "phone_first": [
                enabled_when("phone", when=lambda v, c: True),
            ],
        })
    ]
    u = umpire(fields, rules)
    result = u.check({"email": "a@b.com", "phone": "555"})
    # Both branches pass (each has single target that passes).
    # First branch "email_first" wins → its snapshot applied wholesale.
    # email_first snapshot: email enabled, phone at default (enabled=True)
    assert result["email"].enabled is True
    assert result["phone"].enabled is True
