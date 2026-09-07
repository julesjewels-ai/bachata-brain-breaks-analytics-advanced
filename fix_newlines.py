with open('scripts/entropy.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'report = "# [Entropy] Maintenance - Liability Reduction' in line:
        new_lines.append('    report = "# [Entropy] Maintenance - Liability Reduction\\n\\n"\n')
    elif 'report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |' in line:
        new_lines.append('    report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\\n"\n')
    elif 'report += "|---|---|---|---|---|' in line:
        new_lines.append('    report += "|---|---|---|---|---|\\n"\n')
    else:
        new_lines.append(line)

with open('scripts/entropy.py', 'w') as f:
    f.writelines(new_lines)
