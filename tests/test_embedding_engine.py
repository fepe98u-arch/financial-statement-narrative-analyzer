import pytest

from app.analysis.embedding_engine import LocalModelNotInstalledError, is_model_available, load_model


def test_missing_path_is_not_available():
    assert is_model_available(None) is False
    assert is_model_available("C:/definitely/not/a/real/path/xyz") is False


def test_load_model_raises_clear_error_when_not_installed():
    with pytest.raises(LocalModelNotInstalledError):
        load_model("C:/definitely/not/a/real/path/xyz")


def test_empty_directory_is_not_a_valid_model(tmp_path):
    empty_dir = tmp_path / "empty_model"
    empty_dir.mkdir()
    assert is_model_available(empty_dir) is False
