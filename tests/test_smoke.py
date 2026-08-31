"""Smoke test: verify the package imports and has a version string."""


def test_import_package() -> None:
    import robotsix_calendar

    assert isinstance(robotsix_calendar.__version__, str)
