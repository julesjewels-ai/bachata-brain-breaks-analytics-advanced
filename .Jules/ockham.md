## 2024-05-22 - [Manual Iteration over Groups] **Observation:** The `detect_outliers` method in `src/core/app.py` manually iterates over hardcoded video types ('Shorts', 'Long') to filter dataframes, which is non-idiomatic in Pandas and brittle if new types are added. **Action:** Refactor to use `df.groupby('type')` to handle groups dynamically and idiomatically.

## 2025-02-14 - [Dead Code (dry_run)] **Observation:** The `dry_run` parameter was passed through `main.py` to `BachataAnalyticsApp` but never used in any logic (ingestion or analysis). **Action:** Removed `dry_run` parameter and argument to reduce confusion and cognitive load.

## 2025-02-14 - [Duplicated Logic] **Observation:** Formatting logic for dataframes was duplicated in `src/core/app.py` and `src/core/formatting.py`. **Action:** Extracted `prepare_display_dataframe` to `src/core/formatting.py` and reused it.

## 2025-02-18 - [Duplicated Header Mapping] **Observation:** `src/core/reporting.py` repeated the logic for mapping header names to column indices in 3 different places (`_apply_number_formats`, `_apply_conditional_formatting`, `generate_excel`). **Action:** Extracted `_get_header_map` helper method to consolidate this logic.

## 2025-02-18 - [Dead Code (formatting)] **Observation:** `format_dataframe_for_display` in `src/core/formatting.py` was not used in the application flow (which uses `RichConsoleUI` and `prepare_display_dataframe`). **Action:** Removed the unused function and its tests.

## 2025-02-18 - [Long Function (generate_excel)] **Observation:** `generate_excel` in `src/core/reporting.py` was 60+ lines long and mixed sheet creation, styling, and charting logic. **Action:** Extracted `_create_anomaly_sheet`, `_add_anomaly_chart`, `_add_strategy_sheet`, and `_add_visual_insights` helper methods to reduce complexity.

## 2026-02-02 - [Flattened Arrow Code] **Observation:** `_estimate_cell_width` in `src/core/reporting.py` had nested `if` statements increasing cognitive load. **Action:** Refactored to use guard clauses and early returns for flatter logic.

## 2026-02-03 - [Extracted Method] **Observation:** `_estimate_cell_width` in `src/core/reporting.py` mixed width estimation logic with specific number formatting rules, keeping complexity high (8). **Action:** Extracted `_get_formatted_width` to handle specific format logic, reducing `_estimate_cell_width` complexity to 4.
