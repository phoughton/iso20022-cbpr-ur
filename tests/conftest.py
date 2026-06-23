import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
