import ast
from typing import Dict

def calculate_complexity(node: ast.AST) -> int:
    """
    Calculates the McCabe cyclomatic complexity of an AST node.
    """
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                              ast.ExceptHandler, ast.With, ast.AsyncWith,
                              ast.BoolOp, ast.Match)):
            complexity += 1
    return complexity

def score_code_complexity(content: str) -> Dict[str, int]:
    """
    Returns a dictionary of function names to their cyclomatic complexity score.
    """
    try:
        tree = ast.parse(content)
    except Exception:
        return {}

    complexities = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexities[node.name] = calculate_complexity(node)
    
    return complexities
