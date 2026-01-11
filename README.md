# Bachata Brain Breaks Analytics Advanced

A comprehensive analytics dashboard for 'Bachata Brain Breaks' that ingests channel data to visualize audience demographics and retention curves. It implements statistical outlier detection to isolate viral anomalies in Shorts and Long-form videos, coupled with a specialized Gemini 3 'Thinking Mode' agent that analyzes semantic patterns in the Top/Bottom 5 performers to generate high-conversion title and thumbnail strategies.

## Tech Stack

- Python
- Streamlit
- Pandas
- YouTube Data API v3
- Gemini 3 API
- Plotly

## Features

- Audience Persona & Content Gap Analysis
- Statistical Outlier Detection (Z-Score)
- Top/Bottom 5 Comparative Context Window
- Gemini 3 Thinking Mode Agent
- AI-Generated Title & Thumbnail Blueprints
- Performance Heatmaps

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd bachata-brain-breaks-analytics-advanced
make install

# Run the application
make run
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
make install && make run
```

## Development

```bash
make install  # Create venv and install dependencies
make run      # Run the application
make test     # Run tests
make clean    # Remove cache files
```

## Testing

```bash
pytest tests/ -v
```
