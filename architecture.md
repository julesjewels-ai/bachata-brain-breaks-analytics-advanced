# Bachata Brain Breaks Analytics Advanced - Architecture

## System Overview
The **Bachata Brain Breaks Analytics Advanced** tool is a robust Command-Line Interface (CLI) application designed to ingest YouTube channel data, perform statistical analysis on audience demographics and retention curves, and generate AI-driven content strategies.

The project relies on an asynchronous architecture powered by Python `asyncio`, utilizing Dependency Injection (DI) to compose different services, minimizing tight coupling.

## Core Components (`src/core/`)

The application is structured into several discrete modules:

### 1. `app.py` (Application Lifecycle)
The `BachataAnalyticsApp` class orchestrates the entire application flow:
- Initializing the CLI interface (`ui.py`).
- Pulling simulation or real data (`ingestion.py`).
- Running AI analysis via the Gemini agent (`ai.py`).
- Generating Excel reports and charts (`reporting.py`).
- Firing off notifications (`notifications.py`).

### 2. `ai.py` and `caching.py` (Intelligence Layer)
The core AI processing is handled by the `GeminiThinkingAgent`, which interfaces with the Gemini 3 API to analyze top and bottom performing videos.
To avoid redundant API calls and save costs, the system uses a caching decorator pattern defined in `caching.py`. The `CachedAIService` wraps the base `GeminiThinkingAgent` and stores responses locally.

### 3. `ingestion.py` (Data Pipeline)
Handles the data ingestion process. Currently features a `SimulationDataIngestionService` which generates mock data representing typical YouTube metrics (demographics, retention curves, view outliers) for testing and offline development.

### 4. `reporting.py` and `visualization.py` (Outputs)
- `visualization.py` generates heatmaps and retention curve plots using `matplotlib`.
- `reporting.py` manages the creation of structured Excel workbooks (`.xlsx`) using `openpyxl`, styling them appropriately and embedding generated charts directly into the reports via the `excel_styling.py` and `formatting.py` utilities.

### 5. `interfaces.py` (Contracts)
Defines abstract base classes (ABCs) such as `AIService`, allowing easy swapping of implementations. This facilitates testing by enabling the use of mock services (as seen in `tests/test_core.py`).

## Testing Strategy (`tests/`)

The application embraces unit testing utilizing the `pytest` framework, `pytest-asyncio` for async tests, and `pytest-mock` for dependency mocking. 
- Mocks are primarily applied to the `AIService` and `DataIngestionService` to test core application logic without triggering real network requests.
- The `tests/` directory strictly follows pytest naming conventions.

## Configuration & Environment (`config.py`)
Uses `pydantic` for structured, type-safe settings management. The environment variables are loaded from a `.env` file (see `.env.example`).
