from umpire import FieldDef, umpire
from umpire.rules import any_of, disables, either_of, enabled_when, one_of, requires
from umpire.types import GraphEdge, UmpireGraph


def test_graph_nodes_include_all_fields() -> None:
    u = umpire({"email": FieldDef(), "name": FieldDef()})
    g = u.graph()
    assert "email" in g.nodes
    assert "name" in g.nodes
    assert len(g.nodes) == 2


def test_graph_requires_edge() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    g = u.graph()
    assert GraphEdge(source="b", target="a", kind="requires") in g.edges
    assert len(g.edges) == 1


def test_graph_disables_edge() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef(), "c": FieldDef()},
        [disables("a", ["b", "c"])],
    )
    g = u.graph()
    assert GraphEdge(source="a", target="b", kind="disables") in g.edges
    assert GraphEdge(source="a", target="c", kind="disables") in g.edges
    assert len(g.edges) == 2


def test_graph_empty_source_disables_no_edge() -> None:
    u = umpire(
        {"target": FieldDef()},
        [disables("", ["target"])],
    )
    g = u.graph()
    assert "" not in g.nodes
    assert len(g.edges) == 0


def test_graph_no_edge_for_enabled_when() -> None:
    u = umpire(
        {"a": FieldDef()},
        [enabled_when("a", lambda v, c: True)],
    )
    g = u.graph()
    assert len(g.edges) == 0


def test_graph_no_edge_for_predicate_only_requires() -> None:
    u = umpire(
        {"a": FieldDef()},
        [requires("a", when=lambda v, c: True)],
    )
    g = u.graph()
    assert len(g.edges) == 0


def test_graph_one_of_edges() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef(), "c": FieldDef()},
        [one_of("g", {"x": ["a", "b"], "y": ["c"]})],
    )
    g = u.graph()
    assert GraphEdge(source="a", target="c", kind="one_of") in g.edges
    assert GraphEdge(source="c", target="a", kind="one_of") in g.edges
    assert GraphEdge(source="b", target="c", kind="one_of") in g.edges
    assert GraphEdge(source="c", target="b", kind="one_of") in g.edges
    assert len(g.edges) == 4


def test_graph_any_of_includes_inner_edges() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [any_of([requires("a", "b")])],
    )
    g = u.graph()
    assert GraphEdge(source="b", target="a", kind="requires") in g.edges
    assert len(g.edges) == 1


def test_graph_either_of_includes_inner_edges() -> None:
    """Test either_of rule includes inner requires edge."""
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [either_of("g", {"x": [requires("a", "b")]})],
    )
    g = u.graph()
    assert GraphEdge(source="b", target="a", kind="requires") in g.edges
    assert len(g.edges) == 1


def test_graph_empty_no_fields() -> None:
    """Test graph with no fields or rules returns empty graph."""
    u = umpire({})
    g = u.graph()
    assert g.nodes == ()
    assert g.edges == ()


def test_graph_fresh_immutable() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    g1 = u.graph()
    g2 = u.graph()
    assert g1 == g2
    assert g1 is not g2
    assert isinstance(g1, UmpireGraph)
    assert isinstance(g1.nodes, tuple)
    assert isinstance(g1.edges, tuple)
