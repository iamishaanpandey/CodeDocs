import pytest
from app.services.ingestion.ast_parser import parse_python_file

def test_parse_python_file_success(sample_python_code):
    result = parse_python_file(sample_python_code, "test.py")
    assert "error" not in result
    assert len(result["functions"]) == 3
    assert len(result["classes"]) == 1
    
    process_payment = next(f for f in result["functions"] if f["name"] == "process_payment")
    assert process_payment["args"] == ["user_id", "amount", "card_number"]
    assert process_payment["docstring"] == "Process a payment."
    assert process_payment["returns"] == "dict"

def test_parse_python_file_syntax_error():
    result = parse_python_file("def broken_func(:", "test.py")
    assert "error" in result
    assert result["functions"] == []
    assert result["classes"] == []

def test_parse_python_file_async(sample_fastapi_code):
    result = parse_python_file(sample_fastapi_code, "test.py")
    assert "error" not in result
    assert len(result["functions"]) == 3
    
    get_user = next(f for f in result["functions"] if f["name"] == "get_user")
    assert get_user["is_async"] is True
    assert "current_user" in get_user["args"]
