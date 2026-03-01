# Bachata Brain Breaks Analytics Advanced

A comprehensive analytics command-line dashboard for 'Bachata Brain Breaks' that ingests channel data to visualize audience demographics and retention curves. It implements statistical outlier detection to isolate viral anomalies in Shorts and Long-form videos, coupled with a specialized Gemini 3 'Thinking Mode' agent that analyzes semantic patterns in the Top/Bottom 5 performers to generate high-conversion title and thumbnail strategies.

## Documentation

- **[User Guide](userguide.md)**: Setup, Installation, and Command Reference.
- **[Developer Architecture](architecture.md)**: System design and module breakdown.

## Tech Stack

- Python CLI (Rich)
- Pandas
- YouTube Data API v3
- Gemini 3 API
- Plotly / Matplotlib

## Features

- Audience Persona & Content Gap Analysis
- Statistical Outlier Detection (Z-Score)
- Top/Bottom 5 Comparative Context Window
- Gemini 3 Thinking Mode Agent
- AI-Generated Title & Thumbnail Blueprints
- Performance Heatmaps

## Quick Start
*See [User Guide](userguide.md) for detailed setup instructions.*

```bash
git clone <repo-url>
cd bachata-brain-breaks-analytics-advanced
make install
make run
```

## Development & Testing
*See [Developer Architecture](architecture.md) for details.*

```bash
make install  # Create venv and install dependencies
make test     # Run Pytest tests
make run      # Run the CLI application
make clean    # Remove cache files
```

