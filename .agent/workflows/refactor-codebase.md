---
description: refactor a codebase or specific files
---
1. Use the `view_file` or `grep_search` tools to understand the current structure and identify areas of improvement in the provided files or codebase.
2. If working with a Python project, invoke the `python-pro` skill to ensure modern, production-ready Python practices are followed, and `python-testing-patterns` to ensure sufficient test coverage before refactoring.
3. Invoke the `clean-code` skill to apply Robert C. Martin's principles (readability, maintainability, minimal technical debt) regardless of the language.
4. If working with a Python project, run `pytest` (e.g. `make test`) before making changes to establish a baseline.
5. Apply the refactoring changes using appropriate editing tools (`replace_file_content` or `multi_replace_file_content`).
6. Run tests to ensure no functionality was broken during the refactoring process (e.g. `make test`).
7. Review the changes and ensure they meet the defined standards.
