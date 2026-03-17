# Bachata Brain Breaks Analytics Advanced

A comprehensive analytics CLI dashboard for the **Bachata Brain Breaks** YouTube channel. It ingests channel data (live or simulated), visualises audience demographics and retention curves, applies statistical outlier detection to isolate viral anomalies in Shorts and Long-form content, and runs a specialised **Gemini 3 Thinking-Mode agent** that analyses semantic patterns across Top/Bottom performers to generate actionable title & thumbnail strategies.

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Key Features

- **Audience Persona & Content-Gap Analysis** — AI-generated profiles and strategic content recommendations.
- **Statistical Outlier Detection** — quantile-based identification of viral anomalies across Shorts and Long-form video types.
- **Gemini 3 Thinking-Mode Agent** — streaming AI analysis comparing the Top 5 vs Bottom 5 performers by retention rate.
- **AI-Generated Title & Thumbnail Blueprints** — high-conversion strategies output directly to the console.
- **Excel Reporting** — rich `.xlsx` workbooks with styled heatmaps, retention-curve charts, and embedded images via `openpyxl`.
- **Dual Data Modes** — seamlessly switch between simulated data (for development) and live YouTube Data API v3 data.
- **Rich Console UI** — beautiful terminal output powered by [Rich](https://github.com/Textualize/rich) with tables, spinners, and streaming text.
- **AI Response Caching** — file-based cache layer to avoid redundant Gemini API calls and save costs.
- **Telemetry & Notifications** — structured event logging (`notifications.jsonl`, `telemetry_metrics.jsonl`) with composite notification services.
- **Security Validation** — Pydantic models with prompt-injection detection and formula-injection prevention baked into every data input.

---

## Tech Stack

| Layer            | Technology                                                                 |
| ---------------- | -------------------------------------------------------------------------- |
| **Language**     | Python 3.11+                                                               |
| **Async**        | `asyncio`                                                                  |
| **AI Engine**    | [Google GenAI SDK](https://pypi.org/project/google-genai/) (Gemini 3 API)  |
| **Data**         | Pandas ≥ 2.0, NumPy < 2.0                                                 |
| **YouTube**      | YouTube Data API v3 via `aiohttp`                                          |
| **Validation**   | Pydantic ≥ 2.0                                                             |
| **CLI / UI**     | Rich ≥ 13.0                                                                |
| **Visualisation**| Matplotlib ≥ 3.8, Pillow ≥ 10.0                                           |
| **Reporting**    | openpyxl ≥ 3.1                                                             |
| **Testing**      | pytest, pytest-asyncio, pytest-mock, pytest-cov                            |
| **Type Checking**| mypy                                                                       |
| **Config**       | python-dotenv + Pydantic `BaseModel`                                       |

---

## Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.11 or higher** (the `Makefile` targets `python3.11`)
- **pip** (bundled with Python)
- **Git**

You will also need API keys (see [Configuration](#configuration)):

- A **Google Gemini API key** — required for AI analysis.
- A **YouTube Data API v3 key** — required only when using the `--real-data` flag.
- A **YouTube Channel ID** — required only when using the `--real-data` flag.

> **Note:** The application can run entirely in **simulation mode** (the default) without any API keys, which is ideal for development and testing.

---

## Getting Started

### 1. Clone the Repository

```bash
git clone <repo-url>
cd bachata-brain-breaks-analytics-advanced
```

### 2. Install Dependencies

The `Makefile` handles virtual-environment creation and dependency installation in one step:

```bash
make install
```

This runs:
1. `python3.11 -m venv venv` — creates an isolated virtual environment.
2. `pip install -r requirements.txt` — installs all pinned dependencies.

### 3. Configure Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your text editor (see the [Configuration](#configuration) section below for details on each variable).

### 4. Run the Application

**Simulation mode** (no API keys required):

```bash
make run
```

**Real data from YouTube**:

```bash
make run-real
```

Or run directly with Python:

```bash
source venv/bin/activate
python main.py              # simulation mode
python main.py --real-data  # live YouTube data
```

---

## Configuration

All configuration is managed through a `.env` file at the project root. The application uses Pydantic for type-safe settings validation.

### Environment Variables

| Variable               | Required | Description                                                           | Default                |
| ---------------------- | -------- | --------------------------------------------------------------------- | ---------------------- |
| `GEMINI_API_KEY`       | Yes*     | API key for Google Gemini. Also accepted as `GOOGLE_API_KEY`.         | —                      |
| `YOUTUBE_DATA_API_KEY` | No**     | API key for YouTube Data API v3. Also accepted as `YOUTUBE_API_KEY`.  | —                      |
| `YOUTUBE_CHANNEL_ID`   | No**     | Default YouTube channel to fetch data for.                            | —                      |
| `DEBUG_MODE`           | No       | Enable debug logging.                                                 | `True`                 |
| `APP_ENV`              | No       | Runtime environment (`development`, `production`, `testing`).         | `development`          |
| `AI_CACHE_DIR`         | No       | Directory for caching AI responses.                                   | `.cache/ai_responses`  |

> \* Required for AI analysis; the app will fall back gracefully if missing but the Gemini analysis step will fail.
>
> \*\* Required only when using the `--real-data` flag. In simulation mode these are not needed.

### Example `.env`

```env
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_DATA_API_KEY=your_youtube_key_here
YOUTUBE_CHANNEL_ID=your_channel_id_here
DEBUG_MODE=True
```

---

## Usage

### Command-Line Arguments

| Argument       | Description                                                                                          |
| -------------- | ---------------------------------------------------------------------------------------------------- |
| `--version`    | Print the application version and exit.                                                              |
| `--real-data`  | Use live YouTube Data API v3 instead of simulation.                                                  |
| `--channel-id` | YouTube Channel ID to fetch data for. Overrides `YOUTUBE_CHANNEL_ID` from `.env`.                    |

### Examples

```bash
# Show version
python main.py --version

# Run with simulated data (default)
python main.py

# Run with live YouTube data (uses YOUTUBE_CHANNEL_ID from .env)
python main.py --real-data

# Run with live data for a specific channel
python main.py --real-data --channel-id UC_x5XG1OV2P6uZZ5FSM9Ttw
```

### What to Expect

1. **Data Ingestion** — The tool loads viewer completion data and demographic statistics (simulated or live).
2. **Outlier Detection** — Statistical quantile analysis identifies viral anomalies (> 90th percentile views) across Shorts and Long-form video categories.
3. **AI Analysis** — A Gemini 3 Thinking-Mode agent streams a detailed comparison of the Top 5 vs Bottom 5 performers by retention rate, producing actionable Title & Thumbnail strategies.
4. **Report Generation** — A styled `.xlsx` Excel report is generated with embedded heatmaps and retention-curve charts.
5. **Notifications** — Events are logged to `notifications.jsonl` and displayed in the console.

---

## Architecture

### High-Level Overview

The application follows a **Dependency-Injection (DI)** architecture using Python `Protocol` interfaces. Services are composed in `main.py` and injected into the core `BachataAnalyticsApp` controller, enabling easy swapping of implementations (e.g., simulation ↔ live YouTube data, or real AI ↔ mock for tests).

```
main.py (composition root)
  └── BachataAnalyticsApp
        ├── UserInterface      ← RichConsoleUI
        ├── AIService          ← CachedAIService → GeminiThinkingAgent
        ├── ReportGenerator    ← MetricsReportGenerator → ExcelReportGenerator
        ├── DataIngestionService ← MetricsDataIngestionService → Sim / YouTube
        └── NotificationService  ← CompositeNotificationService
```

### Directory Structure

```
bachata-brain-breaks-analytics-advanced/
├── main.py                    # Entry point & dependency composition
├── Makefile                   # Build, run, test, clean commands
├── requirements.in            # Top-level dependencies
├── requirements.txt           # Pinned dependencies
├── .env.example               # Template for environment variables
├── mypy.ini                   # Type-checking configuration
├── architecture.md            # Detailed architecture documentation
├── userguide.md               # End-user setup guide
│
├── src/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── ai.py              # GeminiThinkingAgent (Gemini 3 API client)
│       ├── app.py             # BachataAnalyticsApp (main controller)
│       ├── caching.py         # CachedAIService & FileCacheBackend
│       ├── charting.py        # Chart helpers for Excel embedding
│       ├── config.py          # AppConfig (Pydantic settings)
│       ├── excel_styling.py   # Excel workbook styling utilities
│       ├── formatting.py      # Display & validation error formatting
│       ├── ingestion.py       # SimulationDataIngestionService
│       ├── interfaces.py      # Protocol contracts (ABCs)
│       ├── metrics.py         # FileMetricsRepository & MetricsReportGenerator
│       ├── models.py          # Pydantic domain models
│       ├── notifications.py   # Console, File & Composite notification services
│       ├── reporting.py       # ExcelReportGenerator (openpyxl)
│       ├── ui.py              # RichConsoleUI (Rich-powered terminal UI)
│       ├── visualization.py   # MatplotlibVisualizer (charts & heatmaps)
│       ├── youtube.py         # YouTubeAPIClient (aiohttp + Data API v3)
│       └── youtube_ingestion.py # YouTubeIngestionService
│
└── tests/
    ├── __init__.py
    ├── snapshots/             # Test snapshot data
    ├── test_caching.py        # AI caching layer tests
    ├── test_charting.py       # Charting utility tests
    ├── test_config.py         # Configuration validation tests
    ├── test_formatting.py     # Formatting utility tests
    ├── test_notification_integration.py  # Notification integration tests
    ├── test_notifications.py  # Notification unit tests
    ├── test_reporting.py      # Excel report generation tests
    ├── test_security_validation.py # Injection prevention & model validation
    ├── test_ui_unit.py        # Rich UI component tests
    ├── test_visualization.py  # Matplotlib visualiser tests
    ├── test_youtube.py        # YouTube API client tests
    └── test_youtube_ingestion.py # YouTube ingestion service tests
```

### Request Lifecycle

```
CLI Args → main.py → AppConfig.get_config()
                   → DataIngestionService.ingest_data()
                   → BachataAnalyticsApp.detect_outliers()
                   → AIService.analyze_stream()
                   → ReportGenerator.generate_report()
                   → NotificationService.notify()
```

### Key Design Decisions

| Decision                  | Rationale                                                                 |
| ------------------------- | ------------------------------------------------------------------------- |
| **Protocol-based DI**     | All core services implement Python `Protocol` interfaces for testability. |
| **Decorator pattern**     | `CachedAIService` wraps `GeminiThinkingAgent`; `MetricsReportGenerator` wraps `ExcelReportGenerator`. |
| **Async-first**           | `asyncio` used throughout for YouTube API calls and AI streaming.         |
| **Pydantic validation**   | All data inputs validated with regex, length, and injection checks.       |
| **Composite notifications** | Console + file logging via a composite service pattern.                |

### Domain Models

| Model                | Purpose                                                      |
| -------------------- | ------------------------------------------------------------ |
| `VideoAnalysisInput` | Validated schema for video data sent to the AI agent.        |
| `NotificationEvent`  | Structured event for the notification system.                |
| `MetricEvent`        | Telemetry event for system-level metrics tracking.           |

---

## Testing

The project uses **pytest** with async support, mocking, and coverage reporting.

### Running Tests

```bash
# Run all tests
make test

# Or directly with pytest (inside the venv)
source venv/bin/activate
pytest

# Run a specific test file
pytest tests/test_caching.py

# Run tests matching a keyword
pytest -k "test_security"

# Run with coverage report
pytest --cov=src --cov-report=term-missing
```

### Testing Approach

- **Mocks** are applied to `AIService` and `DataIngestionService` via `pytest-mock` to test core logic without network requests.
- **`pytest-asyncio`** enables testing of async methods like `ingest_data()` and `analyze_stream()`.
- **Security tests** explicitly verify prompt-injection and formula-injection prevention in `VideoAnalysisInput`.

---

## Troubleshooting

### Gemini API Errors

**Error:** `Failed to generate analysis: ...`

**Solution:**
1. Verify your `GEMINI_API_KEY` is set correctly in `.env`.
2. Ensure you have access to a model that supports thinking/streaming.
3. Check your API quota and billing status in the [Google AI Studio](https://aistudio.google.com/).

### Caching Errors

**Error:** Stale or corrupted cache responses.

**Solution:**
```bash
rm -rf .cache/
```

The cache will be rebuilt automatically on the next run.

### YouTube API Errors

**Error:** `Failed to initialize YouTube service: ...`

**Solution:**
1. Verify `YOUTUBE_DATA_API_KEY` is set in `.env`.
2. Check that the YouTube Data API v3 is enabled in your Google Cloud project.
3. Ensure the `--channel-id` or `YOUTUBE_CHANNEL_ID` is a valid channel ID (starts with `UC`).

### Dependency Installation Issues

**Error:** `pip install` failures or missing native extensions.

**Solution:**
```bash
# Ensure Python 3.11 is available
python3.11 --version

# Clean and reinstall
make clean
make install
```

### Virtual Environment Not Activated

**Error:** `ModuleNotFoundError: No module named 'rich'`

**Solution:**
```bash
source venv/bin/activate
```

All `make` commands activate the venv automatically, but if you run `python main.py` directly you must activate it first.

### Configuration Validation Errors

**Error:** `Configuration Error: ...` or `ValidationError`

**Solution:**
Ensure your `.env` file matches the format in `.env.example`. The `APP_ENV` variable must be one of: `development`, `production`, or `testing`.

