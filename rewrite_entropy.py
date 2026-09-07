import re

with open('scripts/entropy.py', 'r') as f:
    content = f.read()

mapping_func = """
def map_imports(file_path: str) -> List[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
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
"""

# Insert mapping func before parse_ast_for_rot
content = content.replace("def parse_ast_for_rot", mapping_func + "\n" + "def parse_ast_for_rot")

# Update main to use it
main_update = """        health.is_critical_path = tf in critical_paths
        health.associated_source_files = map_imports(tf)
        health.churn_rate = get_git_churn(tf)"""

content = content.replace("        health.is_critical_path = tf in critical_paths\n        health.churn_rate = get_git_churn(tf)", main_update)

with open('scripts/entropy.py', 'w') as f:
    f.write(content)
