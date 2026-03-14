import pytest
from app.services.ingestion.complexity_scorer import score_code_complexity, calculate_complexity
import ast

def test_simple_function():
    code = "def foo(): pass"
    scores = score_code_complexity(code)
    assert scores["foo"] == 1

def test_complex_function():
    code = """
def foo(x):
    if x > 0:
        for i in range(x):
            try:
                pass
            except Exception:
                pass
    return x
"""
    scores = score_code_complexity(code)
    assert scores["foo"] == 4

def test_syntax_error():
    assert score_code_complexity("def foo(") == {}

def test_async_function():
    code = """
async def bar(y):
    async with y as z:
        if z:
            while True:
                pass
"""
    scores = score_code_complexity(code)
    assert scores["bar"] == 4
