import re

with open('scripts/entropy.py', 'r') as f:
    content = f.read()

# We'll use string replacement and ast literal_eval to find things that can be externalized.
# Since Python ast.unparse is available in Python 3.9+ and we are on 3.11, we can actually use it!

new_strategy_a = """def externalize_snapshots(file_path: str) -> bool:
    \"\"\"Strategy A: The Bloat reducer\"\"\"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        class SnapshotTransformer(ast.NodeTransformer):
            def __init__(self, file_path):
                self.modified = False
                self.snapshot_counter = 1
                self.file_path = file_path
                self.snapshots_dir = os.path.join(os.path.dirname(file_path), "snapshots")

            def visit_Dict(self, node):
                self.generic_visit(node)
                # Check if it's large enough (e.g. > 5 keys or token cost)
                if len(node.keys) > 3:
                    try:
                        # Attempt to evaluate to see if it's a pure literal
                        val = ast.literal_eval(node)

                        os.makedirs(self.snapshots_dir, exist_ok=True)
                        base_name = os.path.basename(self.file_path).replace('.py', '')
                        snap_name = f"{base_name}_snap_{self.snapshot_counter}.json"
                        snap_path = os.path.join(self.snapshots_dir, snap_name)

                        with open(snap_path, "w") as sf:
                            json.dump(val, sf, indent=2)

                        self.snapshot_counter += 1
                        self.modified = True

                        # Replace node with load_snapshot call
                        # Assuming a load_snapshot helper exists or we can just use json.load
                        # For simplicity, we inject: json.load(open('path/to/snap.json'))
                        new_node = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='json', ctx=ast.Load()),
                                attr='load',
                                ctx=ast.Load()
                            ),
                            args=[
                                ast.Call(
                                    func=ast.Name(id='open', ctx=ast.Load()),
                                    args=[
                                        ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Attribute(
                                                    value=ast.Name(id='os', ctx=ast.Load()),
                                                    attr='path',
                                                    ctx=ast.Load()
                                                ),
                                                attr='join',
                                                ctx=ast.Load()
                                            ),
                                            args=[
                                                ast.Call(
                                                    func=ast.Attribute(
                                                        value=ast.Attribute(
                                                            value=ast.Name(id='os', ctx=ast.Load()),
                                                            attr='path',
                                                            ctx=ast.Load()
                                                        ),
                                                        attr='dirname',
                                                        ctx=ast.Load()
                                                    ),
                                                    args=[ast.Name(id='__file__', ctx=ast.Load())],
                                                    keywords=[]
                                                ),
                                                ast.Constant(value="snapshots"),
                                                ast.Constant(value=snap_name)
                                            ],
                                            keywords=[]
                                        ),
                                        ast.Constant(value="r")
                                    ],
                                    keywords=[]
                                )
                            ],
                            keywords=[]
                        )
                        return ast.copy_location(new_node, node)
                    except Exception:
                        pass
                return node

        transformer = SnapshotTransformer(file_path)
        new_tree = transformer.visit(tree)

        if transformer.modified:
            # We need to ensure json and os are imported
            imports_to_add = []
            has_json = any(isinstance(n, ast.Import) and any(alias.name == 'json' for alias in n.names) for n in new_tree.body)
            has_os = any(isinstance(n, ast.Import) and any(alias.name == 'os' for alias in n.names) for n in new_tree.body)

            if not has_json:
                imports_to_add.append(ast.Import(names=[ast.alias(name='json', asname=None)]))
            if not has_os:
                imports_to_add.append(ast.Import(names=[ast.alias(name='os', asname=None)]))

            if imports_to_add:
                new_tree.body = imports_to_add + new_tree.body

            ast.fix_missing_locations(new_tree)
            new_content = ast.unparse(new_tree)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return True

    except Exception as e:
        print(f"Error externalizing snapshots in {file_path}: {e}")
        return False
    return False"""

# The original function implementation
old_strategy_a = """def externalize_snapshots(file_path: str) -> bool:
    \"\"\"Strategy A: The Bloat reducer\"\"\"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # We need a robust AST transformer to actually modify the file.
        # For this implementation, we will mock the externalization logic
        # or implement a simple version if possible.

        class SnapshotTransformer(ast.NodeTransformer):
            def __init__(self):
                self.modified = False
                self.snapshot_counter = 1
                self.snapshots = {}

            def visit_Dict(self, node):
                # if dict is large, externalize
                # This is tricky with AST as we lose formatting.
                # A full AST-to-source is needed which might require `astor` or python 3.9+ `ast.unparse`.
                return self.generic_visit(node)

        # To avoid breaking files without a proper round-trip parser, we'll just report it
        # or apply a regex based approach for specific patterns if safe.
        # Given constraints, we will leave it as "Refactored" in report but not physically change it
        # unless we have a safe way to do it. The prompt says: "Externalize Snapshots. Parse the file,
        # identify large inline objects/arrays in expect(), and move them to a separate .json file..."

        # Since Python's AST `unparse` removes comments and formatting, it's destructive.
        # For the sake of the requirement, let's assume we do a safe replacement if we find large dicts.
        pass
    except Exception:
        return False
    return True"""

if old_strategy_a in content:
    content = content.replace(old_strategy_a, new_strategy_a)
else:
    print("Could not find the old strategy A to replace.")

with open('scripts/entropy.py', 'w') as f:
    f.write(content)
