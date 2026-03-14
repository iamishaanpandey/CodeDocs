import ast
from typing import Dict, Any

ENTRY_POINT_FILENAMES = {
    "main.py", "app.py", "server.py", "manage.py", "wsgi.py", "asgi.py", "__init__.py"
}

def is_entry_point(content: str, filename: str) -> Dict[str, Any]:
    """
    Determines if a python file is likely an entry point to the application.
    """
    is_entry = False
    reasons = []

    basename = filename.split("/")[-1].split("\\")[-1]
    if basename in ENTRY_POINT_FILENAMES:
        is_entry = True
        reasons.append(f"Filename '{basename}' is a common entry point")

    try:
        tree = ast.parse(content)
    except Exception:
        return {"is_entry_point": is_entry, "reasons": reasons}

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                if isinstance(left, ast.Name) and left.id == "__name__":
                    if any(isinstance(op, ast.Eq) for op in test.ops):
                        is_entry = True
                        reasons.append("Contains 'if __name__ == \"__main__\":' block")
        
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "app":
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        if node.value.func.id in {"FastAPI", "Flask", "Django"}:
                            is_entry = True
                            reasons.append(f"Instantiates web application ({node.value.func.id})")

    return {"is_entry_point": is_entry, "reasons": list(set(reasons))}
