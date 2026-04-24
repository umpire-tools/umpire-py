"""Example usage of Umpire."""

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


def example_basic_usage() -> None:
    """Basic usage example."""
    # Define fields
    fields = {
        "email": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
        "account_type": FieldDef(required=True, default_value="personal"),
        "company_name": FieldDef(required=False, is_empty=IsEmptyStrategy.STRING),
        "discount_override": FieldDef(),
        "plan_id": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
        "password": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
        "confirm_password": FieldDef(is_empty=IsEmptyStrategy.STRING),
    }

    # Define rules
    rules = [
        # Require company name for business accounts
        requires(
            "company_name",
            when=lambda values, conds: values.get("account_type") == "business",
            reason="Company name is required for business accounts",
        ),
        # Enable confirm_password only after password is satisfied
        requires("confirm_password", dependency="password"),
        # Enable discount override for admin users
        enabled_when(
            "discount_override",
            when=lambda values, conds: conds.get("is_admin") is True,
            reason="Admin only",
        ),
        # Make plan valid based on available plans
        fair_when(
            "plan_id",
            when=lambda values, conds: values.get("plan_id") in (conds.get("valid_plans") or []),
            reason="Plan is not available for this account",
        ),
        # Add validation checks
        check("email", check_ops.email()),
        check("password", check_ops.min_length(8)),
    ]

    # Create Umpire instance
    u = umpire(fields, rules)

    # Check field availability
    result = u.check(
        values={
            "email": "user@example.com",
            "plan_id": "pro",
            "password": "password123",
            "confirm_password": "password123",
        },
        conditions={"is_admin": False, "valid_plans": ["basic", "pro", "enterprise"]},
    )

    # Print results
    for field_name, availability in result.items():
        print(
            f"{field_name}: enabled={availability.enabled}, "
            f"required={availability.required}, fair={availability.fair}, "
            f"satisfied={availability.satisfied}, errors={availability.check_errors}"
        )


if __name__ == "__main__":
    example_basic_usage()
