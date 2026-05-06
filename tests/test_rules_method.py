from umpire import FieldDef, umpire
from umpire.rules import (
    any_of,
    check,
    disables,
    either_of,
    enabled_when,
    fair_when,
    one_of,
    requires,
)


def test_rules_preserves_order() -> None:
    """Test rules() preserves rule order."""

    def always_true(v, c):
        return True

    u = umpire(
        {"email": FieldDef(), "name": FieldDef()},
        [
            requires("email"),
            enabled_when("name", always_true),
        ],
    )
    entries = u.rules()
    assert len(entries) == 2
    assert entries[0].index == 0
    assert entries[0].kind == "requires"
    assert entries[1].index == 1
    assert entries[1].kind == "enabled_when"


def test_rules_deterministic_ids() -> None:
    """Test rules() returns stable, deterministic IDs."""

    def always_true(v, c):
        return True

    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [
            requires("a"),
            enabled_when("b", always_true),
        ],
    )
    first = u.rules()
    second = u.rules()
    # Assert exact expected IDs, not just equality between calls
    assert [e.id for e in first] == ["requires:a", "enabled_when:b"]
    assert [e.id for e in first] == [e.id for e in second]


def test_rules_duplicate_ids_get_suffix() -> None:
    """Test duplicate base IDs get #2, #3 suffixes."""

    def always_true(v, c):
        return True

    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [
            enabled_when("a", always_true),
            enabled_when("a", always_true),
        ],
    )
    entries = u.rules()
    assert len(entries) == 2
    assert entries[0].id == "enabled_when:a"
    assert entries[1].id == "enabled_when:a#2"


def test_rules_three_duplicates_get_suffixes() -> None:
    """Test three identical rules get #2, #3 suffixes."""

    def always_true(v, c):
        return True

    u = umpire(
        {"a": FieldDef()},
        [
            enabled_when("a", always_true),
            enabled_when("a", always_true),
            enabled_when("a", always_true),
        ],
    )
    entries = u.rules()
    assert len(entries) == 3
    assert entries[0].id == "enabled_when:a"
    assert entries[1].id == "enabled_when:a#2"
    assert entries[2].id == "enabled_when:a#3"


def test_rules_kind_and_targets() -> None:
    """Verify kind, targets, and IDs for each rule type."""

    def always_true(v, c):
        return True

    u = umpire(
        {"a": FieldDef(), "b": FieldDef(), "c": FieldDef(), "d": FieldDef()},
        [
            requires("a", "b"),
            enabled_when("c", always_true),
            fair_when("d", always_true),
            disables("a", ["b", "c"]),
            one_of("g", ["a", "b", "c"]),
            any_of([requires("a"), requires("b")]),
            either_of("g2", {"x": [requires("a")], "y": [requires("b")]}),
            check("d", lambda v, f: None),
        ],
    )
    entries = u.rules()
    assert len(entries) == 8

    # requires with dependency
    assert entries[0].id == "requires:a:b"
    assert entries[0].kind == "requires"
    assert entries[0].targets == ("a",)

    # enabled_when
    assert entries[1].id == "enabled_when:c"
    assert entries[1].kind == "enabled_when"
    assert entries[1].targets == ("c",)

    # fair_when
    assert entries[2].id == "fair_when:d"
    assert entries[2].kind == "fair_when"
    assert entries[2].targets == ("d",)

    # disables
    assert entries[3].id == "disables:a"
    assert entries[3].kind == "disables"
    assert entries[3].targets == ("b", "c")

    # one_of
    assert entries[4].id == "one_of:g"
    assert entries[4].kind == "one_of"
    assert entries[4].targets == ("a", "b", "c")

    # any_of
    assert entries[5].id == "any_of"
    assert entries[5].kind == "any_of"
    assert entries[5].targets == ("a", "b")

    # either_of
    assert entries[6].id == "either_of:g2"
    assert entries[6].kind == "either_of"
    assert entries[6].targets == ("a", "b")

    # check
    assert entries[7].id == "check:d"
    assert entries[7].kind == "check"
    assert entries[7].targets == ("d",)


def test_rules_sources() -> None:
    """Verify sources for dependency-backed requires and source-backed disables."""

    def always_true(v, c):
        return True

    u = umpire(
        {"a": FieldDef(), "b": FieldDef(), "c": FieldDef()},
        [
            requires("a", "b"),
            requires("c"),
            disables("b", ["a"]),
            enabled_when("a", always_true),
        ],
    )
    entries = u.rules()
    assert len(entries) == 4

    # requires with dependency: source is the dependency
    assert entries[0].kind == "requires"
    assert entries[0].sources == ("b",)

    # requires without dependency: no sources
    assert entries[1].kind == "requires"
    assert entries[1].sources == ()

    # disables with source: source is rule.source
    assert entries[2].kind == "disables"
    assert entries[2].sources == ("b",)

    # enabled_when: no sources
    assert entries[3].kind == "enabled_when"
    assert entries[3].sources == ()
