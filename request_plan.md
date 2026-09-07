1. **Update configuration files:**
   - Modify `.gitignore` to exclude `.env`, `*.mp4`, `*.mov`, `*.avi`, `*.mkv`, `*.svg`, `coverage.json`, `.coverage`, and `tests/quarantine/`.
   - Modify `.cursorignore` (create if needed) to exclude `tests/quarantine/`.
2. **Implement `scripts/entropy.py`:**
   - Create a Python script that calculates baseline global coverage using `pytest-cov`.
   - Iteratively check each test file's unique coverage using `pytest-cov`.
   - Calculate test inflation metrics: Mock Density, Token Cost, Churn Rate.
   - Use `ast` (specifically `NodeTransformer`, `walk`, `literal_eval`) to detect tautologies and externalize snapshots for Context Bloat safely.
   - Implement Strategy Pattern for Delete, Quarantine, and Refactor.
   - Enforce guardrails: The Vibe Check (abort if >20 files flagged), Preserve Specs (skip `*.md`/`*.feature`), Critical Path Immunity (using `critical_paths.json`).
   - Rerun global coverage; if it drops >0.5%, perform `git restore .` and `git clean -fd`.
   - Output results to `entropy_report.md`.
3. **Automate via GitHub Actions:**
   - Create `.github/workflows/entropy.yml` to run `scripts/entropy.py` daily at 02:00 UTC. Ensure it sets up Python, installs dependencies, and configures Git.
4. **Complete pre-commit steps:**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
5. **Submit the changes:**
   - Run `make test` to verify no regressions in valid tests, and commit the changes using `entropy-automation` branch.
