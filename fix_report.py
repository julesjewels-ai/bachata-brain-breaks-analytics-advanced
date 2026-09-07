with open('scripts/entropy.py', 'r') as f:
    content = f.read()

bad_loop = """    for v in verdicts:
        health_info = next(h for h in [TestFileHealth(v.file) for v in verdicts] ) # we lost health info, let's just format it
        # Recalculate or store it better.
        uc_str = "INF" if v.suggested_action == "NONE" else "???" # placeholder
        report += f"| {v.file} | {', '.join(v.tags)} | 0 lines | {v.suggested_action} | {v.rationale} |\\n\""""

# Instead of recalculating, let's store health objects or just unique coverage inside RotVerdict.
# Update RotVerdict class
new_rot_verdict = """class RotVerdict:
    def __init__(self, file: str):
        self.file = file
        self.score = 0
        self.tags: List[str] = []
        self.suggested_action = "NONE"
        self.rationale = ""
        self.unique_coverage_lines = 0"""

content = content.replace("""class RotVerdict:
    def __init__(self, file: str):
        self.file = file
        self.score = 0
        self.tags: List[str] = []
        self.suggested_action = "NONE"
        self.rationale = \"\"""", new_rot_verdict)

# Update the main assignment
assignment = """        verdict = RotVerdict(tf)
        verdict.unique_coverage_lines = health.unique_coverage_lines"""

content = content.replace("        verdict = RotVerdict(tf)", assignment)


good_loop = """    for v in verdicts:
        uc_str = "INF" if v.unique_coverage_lines == float('inf') else f"{int(v.unique_coverage_lines)} lines"
        report += f"| {v.file} | {', '.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\\n\""""

content = content.replace(bad_loop, good_loop)

with open('scripts/entropy.py', 'w') as f:
    f.write(content)
