import ast
from typing import List, Dict, Any

def scan_for_security_issues(content: str) -> List[Dict[str, Any]]:
    """
    Basic AST-based static analysis for security issues (secrets, eval, exec, sql injection).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id.lower()
                    if any(x in name for x in {"secret", "password", "token", "api_key", "credential"}):
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            if len(node.value.value) > 4: 
                                issues.append({
                                    "type": "hardcoded_secret",
                                    "severity": "HIGH",
                                    "message": f"Potential hardcoded secret assigned to '{target.id}'",
                                    "lineno": node.lineno
                                })

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec"}:
                    issues.append({
                        "type": "dangerous_function",
                        "severity": "HIGH",
                        "message": f"Use of dangerous built-in function '{node.func.id}'",
                        "lineno": node.lineno
                    })

        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in {"execute", "raw"}:
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                issues.append({
                    "type": "sql_injection",
                    "severity": "CRITICAL",
                    "message": "Potential SQL injection: using formatted string (f-string) in DB execute()",
                    "lineno": node.lineno
                })
            elif node.args and isinstance(node.args[0], ast.Call) and getattr(node.args[0].func, "attr", None) == "format":
                issues.append({
                    "type": "sql_injection",
                    "severity": "CRITICAL",
                    "message": "Potential SQL injection: using .format() in DB execute()",
                    "lineno": node.lineno
                })

    return issues
