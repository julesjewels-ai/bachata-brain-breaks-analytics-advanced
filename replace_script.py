import ast

def find_imports(filepath):
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src."):
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("src."):
                    imports.append(node.module)
        return imports
    except Exception:
        return []

print(find_imports("tests/test_youtube_ingestion.py"))
