import pytest
from app.services.ingestion.entry_point_detector import is_entry_point

def test_filename_entry_point():
    result = is_entry_point("print('hello')", "main.py")
    assert result["is_entry_point"] is True
    assert any("Filename" in r for r in result["reasons"])

def test_if_name_main():
    code = "if __name__ == '__main__':\n    pass"
    result = is_entry_point(code, "utils.py")
    assert result["is_entry_point"] is True
    assert any("__main__" in r for r in result["reasons"])

def test_app_instantiation():
    code = "app = FastAPI()"
    result = is_entry_point(code, "api.py")
    assert result["is_entry_point"] is True
    assert any("Instantiates web application" in r for r in result["reasons"])

def test_not_entry_point():
    code = "def helper(): return 1"
    result = is_entry_point(code, "helpers.py")
    assert result["is_entry_point"] is False
    assert result["reasons"] == []
