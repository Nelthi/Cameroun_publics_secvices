import pytest

from gaps.mocks import write_mock_files


@pytest.fixture
def mock_files(tmp_path):
    return write_mock_files(tmp_path / "mock")
