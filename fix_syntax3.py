with open('scripts/entropy.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("\\n"): # catch that stray backslash
        new_lines.append(line.replace("\\n", "\n"))
    elif "nonlocal has_tautology" in line:
        pass # remove
    elif "has_tautology = True" in line:
        new_lines.append(line.replace("has_tautology = True", "state['has_tautology'] = True"))
    elif "has_tautology = False" in line:
        new_lines.append(line.replace("has_tautology = False", "state = {'has_tautology': False}"))
    elif "return mock_density, has_tautology" in line:
        new_lines.append(line.replace("return mock_density, has_tautology", "return mock_density, state['has_tautology']"))
    else:
        new_lines.append(line)

with open('scripts/entropy.py', 'w') as f:
    f.writelines(new_lines)
