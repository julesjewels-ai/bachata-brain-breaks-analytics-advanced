"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""
import random
import logging
from typing import List, Dict
import pandas as pd
from pydantic import BaseModel, Field, field_validator, ValidationError
from src.core.reporting import ExcelReportGenerator
from src.core.config import AppConfig

# Configure logging
logger = logging.getLogger(__name__)

class VideoAnalysisInput(BaseModel):
    """
    Schema for video data to be analyzed by the agent.
    Strictly validates input to prevent injection and ensure data integrity.
    """
    video_id: str = Field(..., pattern=r"^vid_\d+$")
    title: str = Field(..., min_length=1, max_length=200)
    views: int = Field(..., ge=0)
    retention_avg_pct: float = Field(..., ge=0.0, le=100.0)
    type: str = Field(..., pattern=r"^(Shorts|Long)$")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        # Basic sanitization and prompt injection check
        forbidden_patterns = ["Ignore previous instructions", "System:", "User:"]
        for pattern in forbidden_patterns:
            if pattern in v:
                raise ValueError(f"Potential prompt injection detected: {pattern}")
        # Ensure no control characters
        if not v.isprintable():
            raise ValueError("Title contains non-printable characters")
        return v

class GeminiThinkingAgent:
    """
    Simulates Gemini 3 'Thinking Mode' to analyze semantic patterns.
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        Now strictly typed for security.
        """
        if not videos:
            return "No data to analyze."
            
        # Simulated 'Thinking Mode' logic
        return (
            "[Gemini 3 Thinking Mode] Analysis Complete:\n"
            "1. Pattern Identification: High-retention videos often use 'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include 'Step-by-Step' hook."
        )

class BachataAnalyticsApp:
    """
    Main application controller.
    """
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        # Securely load configuration
        self.config = AppConfig.get_config()
        self.agent = GeminiThinkingAgent()

    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data (Shorts and Long-form).
        In a real app, this would connect to YouTube Analytics API.
        """
        print("Ingesting channel data...")
        data = {
            'video_id': [f'vid_{i}' for i in range(1, 21)],
            'title': [
                'Basic Step Tutorial', 'Sensual Bachata Demo', 'Viral Short Dance', 
                'Advanced Footwork', 'Partner Connection Secrets', 'Musicality 101',
                'Funny Bloopers', 'Festival Vlog', 'Dip Technique', 'Spin Drill'
            ] * 2,
            'views': [random.randint(500, 500000) for _ in range(20)],
            'retention_avg_pct': [random.uniform(20.0, 95.0) for _ in range(20)],
            'type': ['Long' if i % 3 != 0 else 'Shorts' for i in range(20)]
        }
        return pd.DataFrame(data)

    def detect_outliers(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Implements statistical outlier detection for viral anomalies.
        """
        results = {}
        for v_type, group in df.groupby('type'):
            # Simple statistical outlier detection using Quantiles (Viral > 90th percentile)
            threshold = group['views'].quantile(0.90)
            results[str(v_type)] = group[group['views'] > threshold]

        return results

    def run(self) -> None:
        """
        Executes the analytics pipeline.
        """
        # 1. Ingest
        df = self.ingest_data()
        print(f"Data loaded: {len(df)} records.")

        # 2. Outlier Detection
        anomalies = self.detect_outliers(df)
        for v_type, data in anomalies.items():
            print(f"\n--- Viral Anomalies ({v_type}) ---")
            print(data[['title', 'views', 'retention_avg_pct']].to_string(index=False))

        # 3. Gemini Analysis (Top/Bottom 5)
        print("\n--- Gemini 3 Agent Analysis ---")
        sorted_df = df.sort_values(by='retention_avg_pct', ascending=False)
        
        top_5_records = sorted_df.head(5).to_dict('records')
        bottom_5_records = sorted_df.tail(5).to_dict('records')

        # Securely validate and convert data
        analysis_input = []
        try:
            for record in top_5_records + bottom_5_records:
                # Ensure keys are strings
                clean_record = {str(k): v for k, v in record.items()}
                validated_item = VideoAnalysisInput(**clean_record)
                analysis_input.append(validated_item)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            # Decide whether to abort or skip. Aborting is safer for security.
            print("Error: Invalid data detected. Aborting analysis for security.")
            return

        strategy = self.agent.analyze_semantics(analysis_input)
        print(strategy)

        # 4. Generate Excel Report
        print("\nGenerating Excel Report...")
        report_gen = ExcelReportGenerator()
        report_gen.generate_excel(anomalies, strategy, "bachata_analytics.xlsx")
        print("Report saved to 'bachata_analytics.xlsx'.")

        print("\nDashboard update complete.")
