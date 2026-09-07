with open('scripts/entropy.py', 'r') as f:
    text = f.read()

# Replace nonlocal with list
text = text.replace("has_tautology = False", "state = [False]")
text = text.replace("nonlocal has_tautology", "")
text = text.replace("has_tautology = True", "state[0] = True")
text = text.replace("return mock_density, has_tautology", "return mock_density, state[0]")

# Make sure we don't have literal \\n in strings where it shouldn't be
text = text.replace('report += f"| {v.file} | {\', \'.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\\\\n\\""', 'report += f"| {v.file} | {\', \'.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\\n"')

with open('scripts/entropy.py', 'w') as f:
    f.write(text)
