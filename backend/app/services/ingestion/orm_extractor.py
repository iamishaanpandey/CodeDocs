import ast
from typing import Dict, List, Any

DB_FIELD_TYPES = {
    "Column", "relationship", "CharField", "IntegerField", "BooleanField", "DateTimeField", "ForeignKey"
}

def extract_orm_models(content: str) -> List[Dict[str, Any]]:
    """
    Extracts basic ORM model structures from a python file (supports SQLAlchemy, Django ORM).
    Returns a list of models with their fields.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    models = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_model = False
            for base in node.bases:
                base_name = ast.unparse(base)
                if "Base" in base_name or "Model" in base_name or base_name in {"models.Model", "db.Model"}:
                    is_model = True
                    break
            
            for body_node in node.body:
                if isinstance(body_node, ast.Assign):
                    for target in body_node.targets:
                        if isinstance(target, ast.Name) and target.id == "__tablename__":
                            is_model = True
                            break

            if is_model:
                fields = []
                for body_node in node.body:
                    if isinstance(body_node, (ast.Assign, ast.AnnAssign)):
                        target_names = []
                        if isinstance(body_node, ast.Assign):
                            for target in body_node.targets:
                                if isinstance(target, ast.Name):
                                    target_names.append(target.id)
                        elif isinstance(body_node, ast.AnnAssign) and isinstance(body_node.target, ast.Name):
                            target_names.append(body_node.target.id)

                        for name in target_names:
                            if name.startswith("__"):
                                continue
                            
                            field_type = "Unknown"
                            if isinstance(body_node, ast.Assign) and isinstance(body_node.value, ast.Call):
                                if isinstance(body_node.value.func, ast.Name) and body_node.value.func.id in DB_FIELD_TYPES:
                                    field_type = body_node.value.func.id
                                elif isinstance(body_node.value.func, ast.Attribute) and body_node.value.func.attr in DB_FIELD_TYPES:
                                    field_type = body_node.value.func.attr

                            elif isinstance(body_node, ast.AnnAssign) and body_node.annotation:
                                field_type = ast.unparse(body_node.annotation)

                            if field_type != "Unknown" or isinstance(body_node, ast.Assign):
                                fields.append({"name": name, "type": field_type})

                models.append({
                    "name": node.name,
                    "fields": fields
                })

    return models
