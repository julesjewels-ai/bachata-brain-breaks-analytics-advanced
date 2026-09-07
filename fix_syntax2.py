with open('scripts/entropy.py', 'r') as f:
    content = f.read()

# Replace the specific lines inside parse_ast_for_rot manually instead of regexing the whole func
content = content.replace("""    has_tautology = False

    class TautologyVisitor(ast.NodeVisitor):
        def visit_Assert(self, node):
            # check if asserting a literal
            if isinstance(node.test, ast.Constant):
                nonlocal has_tautology
                has_tautology = True
            elif isinstance(node.test, ast.Compare):
                # check if comparing two constants like assert True == True
                if isinstance(node.test.left, ast.Constant) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant):
                    if node.test.left.value == node.test.comparators[0].value:
                        nonlocal has_tautology
                        has_tautology = True
            self.generic_visit(node)

    TautologyVisitor().visit(tree)

    return mock_density, has_tautology""", """    state = {'has_tautology': False}

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

    return mock_density, state['has_tautology']""")

with open('scripts/entropy.py', 'w') as f:
    f.write(content)
