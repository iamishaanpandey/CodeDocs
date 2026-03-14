import pytest
from app.services.ingestion.security_scanner import scan_for_security_issues

def test_hardcoded_secret():
    code = "API_KEY = 'sk-1234567890abcdef'"
    issues = scan_for_security_issues(code)
    assert len(issues) == 1
    assert issues[0]["type"] == "hardcoded_secret"
    assert issues[0]["severity"] == "HIGH"

def test_dangerous_function():
    code = "eval('1 + 1')"
    issues = scan_for_security_issues(code)
    assert len(issues) == 1
    assert issues[0]["type"] == "dangerous_function"
    assert issues[0]["severity"] == "HIGH"

def test_sql_injection():
    code = "db.execute(f'SELECT * FROM users WHERE id = {user_id}')"
    issues = scan_for_security_issues(code)
    assert len(issues) == 1
    assert issues[0]["type"] == "sql_injection"
    assert issues[0]["severity"] == "CRITICAL"

def test_secure_code():
    code = "x = 10\nprint(x)\ndb.execute('SELECT * FROM users WHERE id = :id', {'id': user_id})"
    issues = scan_for_security_issues(code)
    assert len(issues) == 0
