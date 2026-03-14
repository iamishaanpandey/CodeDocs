import ast
from typing import List, Dict, Any

EXTERNAL_LIBS = {
    "requests", "httpx", "aiohttp", "urllib", "boto3", "stripe", "twilio", "sendgrid", "google"
}

def detect_external_services(content: str) -> List[Dict[str, Any]]:
    """
    Detects external network/API calls made within the code.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    services = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            service_name = None
            call_type = None

            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in EXTERNAL_LIBS:
                        service_name = node.func.value.id
                        call_type = node.func.attr
                    elif node.func.attr in {"get", "post", "put", "delete", "patch"} and node.func.value.id in {"requests", "httpx", "client", "session"}:
                        service_name = node.func.value.id
                        call_type = node.func.attr

            elif isinstance(node.func, ast.Name):
                if node.func.id in EXTERNAL_LIBS:
                    pass
            
            if service_name:
                url_guess = "Unknown"
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    url_guess = node.args[0].value
                
                services.append({
                    "service": service_name,
                    "method": call_type,
                    "url": url_guess,
                    "lineno": getattr(node, "lineno", 0)
                })

    return services
