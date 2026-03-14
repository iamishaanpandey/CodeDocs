import ast
from typing import Dict, Any, List
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tst
import tree_sitter_java as tsjava
import tree_sitter_cpp as tscpp
import tree_sitter_go as tsgo
import tree_sitter_rust as tsrust
import tree_sitter_ruby as tsruby
import tree_sitter_php as tsphp
import tree_sitter_c_sharp as tscs
import logging

logger = logging.getLogger(__name__)

JS_LANGUAGE = Language(tsjs.language())
TS_LANGUAGE = Language(tst.language_typescript())
TSX_LANGUAGE = Language(tst.language_tsx())
JAVA_LANGUAGE = Language(tsjava.language())
CPP_LANGUAGE = Language(tscpp.language())
GO_LANGUAGE = Language(tsgo.language())
RUST_LANGUAGE = Language(tsrust.language())
RUBY_LANGUAGE = Language(tsruby.language())
PHP_LANGUAGE = Language(tsphp.language())
CSHARP_LANGUAGE = Language(tscs.language())

def parse_python_file(content: str, filepath: str = "") -> Dict[str, Any]:
    """
    Parses a python file content into an AST and extracts functions and classes.
    """
    try:
        tree = ast.parse(content, filename=filepath)
    except Exception as e:
        return {"error": str(e), "functions": [], "classes": []}

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args]
            if getattr(node.args, "vararg", None):
                args.append(f"*{node.args.vararg.arg}")
            if getattr(node.args, "kwarg", None):
                args.append(f"**{node.args.kwarg.arg}")
                
            functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "args": args,
                "returns": ast.unparse(node.returns) if getattr(node, "returns", None) else None,
                "docstring": ast.get_docstring(node),
                "file_path": filepath
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "bases": [ast.unparse(b) for b in node.bases],
                "docstring": ast.get_docstring(node),
                "methods": [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                "file_path": filepath
            })

    # Sort by line number for better readability downstream
    functions.sort(key=lambda x: x["lineno"])
    classes.sort(key=lambda x: x["lineno"])

    return {"functions": functions, "classes": classes}

def parse_general_file(content: str, filepath: str) -> Dict[str, Any]:
    import pathlib
    ext = pathlib.Path(filepath).suffix
    
    js_ts_query = "(function_declaration name: (identifier) @name) @function\n(variable_declarator name: (identifier) @name value: (arrow_function)) @function\n(method_definition name: (property_identifier) @name) @function\n(export_statement (function_declaration name: (identifier) @name)) @function"
    cpp_query = "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @function\n(function_definition declarator: (function_declarator declarator: (qualified_identifier name: (identifier) @name))) @function"
    
    LANGUAGE_MAP = {
        ".js": (JS_LANGUAGE, js_ts_query),
        ".ts": (TS_LANGUAGE, js_ts_query),
        ".tsx": (TSX_LANGUAGE, js_ts_query),
        ".java": (JAVA_LANGUAGE, "(method_declaration name: (identifier) @name) @function\n(constructor_declaration name: (identifier) @name) @function"),
        ".cpp": (CPP_LANGUAGE, cpp_query),
        ".cc": (CPP_LANGUAGE, cpp_query),
        ".cxx": (CPP_LANGUAGE, cpp_query),
        ".c": (CPP_LANGUAGE, cpp_query),
        ".h": (CPP_LANGUAGE, cpp_query),
        ".hpp": (CPP_LANGUAGE, cpp_query),
        ".go": (GO_LANGUAGE, "(function_declaration name: (identifier) @name) @function\n(method_declaration name: (field_identifier) @name) @function"),
        ".rs": (RUST_LANGUAGE, "(function_item name: (identifier) @name) @function"),
        ".rb": (RUBY_LANGUAGE, "(method name: (identifier) @name) @function\n(singleton_method name: (identifier) @name) @function"),
        ".php": (PHP_LANGUAGE, "(function_definition name: (name) @name) @function\n(method_declaration name: (name) @name) @function"),
        ".cs": (CSHARP_LANGUAGE, "(method_declaration name: (identifier) @name) @function\n(constructor_declaration name: (identifier) @name) @function")
    }

    if ext not in LANGUAGE_MAP:
        return {"functions": [], "classes": []}

    language, query_str = LANGUAGE_MAP[ext]
    parser = Parser(language)
    tree = parser.parse(bytes(content, "utf8"))
    functions = []
    
    query = Query(language, query_str)
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)

    processed_nodes = set()
    for node, tag in captures:
        if tag == "function":
            if node.id in processed_nodes:
                continue
            processed_nodes.add(node.id)
            
            name = "anonymous"
            for n, t in captures:
                if t == "name" and n.start_byte >= node.start_byte and n.end_byte <= node.end_byte:
                    name = n.text.decode("utf8")
                    break

            functions.append({
                "name": name,
                "lineno": node.start_point[0] + 1,
                "end_lineno": node.end_point[0] + 1,
                "file_path": filepath
            })

    return {"functions": functions, "classes": []}
