with open('scripts/entropy.py', 'r') as f:
    text = f.read()

# I see the problem. In my earlier rewrite scripts I replaced \n with literal \n which messed up the code when written.
# Let's fix this properly.

text = text.replace("nonlocal has_tautology\n                has_tautology = True", "state[0] = True")
text = text.replace("nonlocal has_tautology\n                        has_tautology = True", "state[0] = True")
text = text.replace("has_tautology = False", "state = [False]")
text = text.replace("return mock_density, has_tautology", "return mock_density, state[0]")

text = text.replace('report += f"| {v.file} | {\', \'.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\\n\\""', 'report += f"| {v.file} | {\', \'.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\\n"')

with open('scripts/entropy.py', 'w') as f:
    f.write(text)
