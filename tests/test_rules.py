from umpire.rules import (
    AnyOfRule,
    CheckRule,
    DisablesRule,
    EnabledWhenRule,
    FairWhenRule,
    OneOfRule,
    RequiresRule,
    any_of,
    check,
    disables,
    enabled_when,
    fair_when,
    one_of,
    requires,
)


def test_requires_rule() -> None:
    """Test requires rule creation."""
    rule = requires("dependent_field", "dependency_field", reason="Dependency required")
    assert isinstance(rule, RequiresRule)
    assert rule.field == "dependent_field"
    assert rule.dependency == "dependency_field"
    assert rule.reason == "Dependency required"


def test_enabled_when_rule() -> None:
    """Test enabled_when rule creation."""

    # Simple predicate function for testing
    def test_predicate(values, conditions):
        return True

    rule = enabled_when("test_field", test_predicate, reason="Enabled when condition met")
    assert isinstance(rule, EnabledWhenRule)
    assert rule.field == "test_field"
    assert rule.when is test_predicate
    assert rule.reason == "Enabled when condition met"


def test_disables_rule() -> None:
    """Test disables rule creation."""

    # Simple predicate function for testing
    def test_predicate(values, conditions):
        return True

    rule = disables(
        "source_field", ["target1", "target2"], test_predicate, reason="Disabled when condition met"
    )
    assert isinstance(rule, DisablesRule)
    assert rule.source == "source_field"
    assert rule.targets == ["target1", "target2"]
    assert rule.when is test_predicate
    assert rule.reason == "Disabled when condition met"


def test_disables_rule_single_target() -> None:
    """Test disables rule creation with single target."""

    # Simple predicate function for testing
    def test_predicate(values, conditions):
        return True

    rule = disables("source_field", "target1", test_predicate, reason="Disabled when condition met")
    assert isinstance(rule, DisablesRule)
    assert rule.source == "source_field"
    assert rule.targets == ["target1"]
    assert rule.when is test_predicate
    assert rule.reason == "Disabled when condition met"


def test_one_of_rule() -> None:
    """Test one_of rule creation."""
    rule = one_of("group1", ["field1", "field2", "field3"], reason="Only one allowed")
    assert isinstance(rule, OneOfRule)
    assert rule.group == "group1"
    assert rule.branches == {
        "field1": ["field1"],
        "field2": ["field2"],
        "field3": ["field3"],
    }
    assert rule.reason == "Only one allowed"


def test_any_of_rule() -> None:
    """Test any_of rule creation."""
    # Create some dummy rules for testing
    rule1 = requires("field1", reason="Field1 required")
    rule2 = requires("field2", reason="Field2 required")

    rule = any_of([rule1, rule2])
    assert isinstance(rule, AnyOfRule)
    assert rule.rules == [rule1, rule2]


def test_fair_when_rule() -> None:
    """Test fair_when rule creation."""

    # Simple predicate function for testing
    def test_predicate(values, conditions):
        return True

    rule = fair_when("test_field", test_predicate, reason="Fair when condition met")
    assert isinstance(rule, FairWhenRule)
    assert rule.field == "test_field"
    assert rule.when is test_predicate
    assert rule.reason == "Fair when condition met"


def test_check_rule() -> None:
    """Test check rule creation."""

    # Create a dummy check op for testing
    class DummyCheckOp:
        pass

    dummy_op = DummyCheckOp()
    rule = check("test_field", dummy_op)
    assert isinstance(rule, CheckRule)
    assert rule.field == "test_field"
    assert rule.op is dummy_op
