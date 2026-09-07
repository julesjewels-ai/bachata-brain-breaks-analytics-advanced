import re

with open('scripts/entropy.py', 'r') as f:
    content = f.read()

# Fix the SyntaxError: name 'has_tautology' is assigned to before nonlocal declaration
# This happens if we do something before nonlocal. Let's just use a list or dict to pass by reference to avoid nonlocal issues.
new_func = """def parse_ast_for_rot(file_path: str) -> tuple[float, bool]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\\n')
    loc = len(lines)

    # Count mock lines roughly
    mock_lines = sum(1 for line in lines if "mock(" in line or "spyOn(" in line or ".mockReturnValue(" in line or "Mock(" in line or "patch(" in line or "MagicMock(" in line or "AsyncMock(" in line)

    mock_density = mock_lines / max(1, loc)

    # Parse AST for tautologies
    try:
        tree = ast.parse(content)
    except Exception:
        return mock_density, False

    state = {'has_tautology': False}

    class TautologyVisitor(ast.NodeVisitor):
        def visit_Assert(self, node):
            # check if asserting a literal
            if isinstance(node.test, ast.Constant):
                state['has_tautology'] = True
            elif isinstance(node.test, ast.Compare):
                # check if comparing two constants like assert True == True
                if isinstance(node.test.left, ast.Constant) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant):
                    if node.test.left.value == node.test.comparators[0].value:
                        state['has_tautology'] = True
            self.generic_visit(node)

    TautologyVisitor().visit(tree)

    return mock_density, state['has_tautology']"""

import ast

def replace_func(source, func_name, new_func_code):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            lines = source.split('\\n')
            # remove old func
            start = node.lineno - 1
            end = node.end_lineno
            return '\\n'.join(lines[:start]) + '\\n' + new_func_code + '\\n' + '\\n'.join(lines[end:])
    return source

content = replace_func(content, 'parse_ast_for_rot', new_func)

with open('scripts/entropy.py', 'w') as f:
    f.write(content)
