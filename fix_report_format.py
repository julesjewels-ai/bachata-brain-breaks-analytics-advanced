with open('scripts/entropy.py', 'r') as f:
    text = f.read()

# Make sure newlines in the report generation are correct
text = text.replace('report = "# [Entropy] Maintenance - Liability Reduction\\n\\n"', 'report = "# [Entropy] Maintenance - Liability Reduction\\n\\n"')

text = text.replace('report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\\n"', 'report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\\n"')
text = text.replace('report += "|---|---|---|---|---|\\n"', 'report += "|---|---|---|---|---|\\n"')

with open('scripts/entropy.py', 'w') as f:
    f.write(text)
