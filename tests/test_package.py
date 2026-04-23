import umpire


def test_package_exposes_version() -> None:
    assert isinstance(umpire.__version__, str)
    assert umpire.__version__
