---
name: Feature Request Workflow
description: A workflow for systematically implementing a feature component by component, keeping track of tasks and validating progress.
---

# Feature Request Workflow

This skill guides the agent in implementing a complex feature by breaking it down into component-level tasks and executing them systematically.

## Workflow Steps

1. **Review Task State**: Always check the `task.md` and `implementation_plan.md` artifacts to see what component is currently mapped out and pending implementation.
2. **Select Next Component**: Pick the next uncompleted `[ ]` item from under the current active feature phase. Update it as in-progress `[/]` via the artifact update.
3. **Implementation**:
    - Write the code for the selected component.
    - Write the associated unit or integration tests for the component.
4. **Validation**:
    - Run the relevant automated tests (e.g., `make test` or `pytest tests/test_core.py`).
    - Verify that no types or linting are broken (if applicable).
5. **Completion**:
    - Mark the item as completed `[x]` in `task.md`.
    - If there are remaining components in the phase, proceed to the next component or ask the user for confirmation to continue.
