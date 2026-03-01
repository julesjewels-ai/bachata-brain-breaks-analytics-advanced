# Bachata Brain Breaks Analytics Advanced - User Guide

This guide will walk you through setting up and running the Bachata Analytics CLI tool to analyze your YouTube data and generate AI content strategies.

## Prerequisites
- Python 3.9+ installed on your system.
- API Keys for Google Gemini and YouTube Data API v3.

## 1. Setup & Installation

Clone the repository and install dependencies using the included `Makefile`:
```bash
git clone <repo-url>
cd bachata-brain-breaks-analytics-advanced
make install
```
*(This commands creates a Python virtual environment (`venv`) and safe-installs all required packages.)*

## 2. Configuration

Next, you need to configure your environment variables. 
Copy the `.env.example` file to create a `.env` file:
```bash
cp .env.example .env
```

Open `.env` in your text editor and fill in your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_DATA_API_KEY=your_youtube_key_here
DEBUG_MODE=True
```

## 3. Running the Application

Execute the CLI tool to start the analysis process:
```bash
make run
```
or manually via Python:
```bash
source venv/bin/activate
python main.py
```

### What to Expect:
1. **Data Ingestion**: The tool will load viewer completion data and demographic statistics.
2. **Analysis**: The system computes statistical z-scores to find "viral anomalies" (outliers) in both Shorts and Long-Form content.
3. **AI Generation**: A Gemini 3 agent analyzes the semantic patterns of your top vs bottom videos, outputting actionable Title & Thumbnail strategies directly to your console.
4. **Report Generation**: An `audience_report_*.xlsx` Excel file is generated, which includes colored heatmaps and retention curve plots.

## Output Files

The application produces the following core outputs:
- `audience_report_YYYYMMDD_HHMMSS.xlsx`: A comprehensive Excel file detailing viewer personas, content gaps, and visually embedded charts.
- `audience_retention_curves.png`: A line graph displaying audience retention over video duration.
- `performance_heatmap.png`: A graphical heatmap showing video metric correlations.

## Troubleshooting

- **Caching Errors**: If you encounter issues with AI requests, try clearing the cache by deleting the generated `./.cache` directory.
- **Dependency Issues**: Make sure you activated your local virtual environment: `source venv/bin/activate`.
