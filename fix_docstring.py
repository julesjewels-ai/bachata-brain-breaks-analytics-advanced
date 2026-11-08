with open("src/core/reporting.py", "r") as f:
    reporting = f.read()

reporting = reporting.replace("import typing\n\"\"\"\nReporting module for generating Excel reports.\n\"\"\"", "\"\"\"\nReporting module for generating Excel reports.\n\"\"\"\nimport typing")

with open("src/core/reporting.py", "w") as f:
    f.write(reporting)
