"""
Service layer for orchestrating analytics tasks.
Follows SOLID principles (SRP, DIP).
"""
import io
from typing import Dict, Any, List
import pandas as pd
from src.core.interfaces import IReportGenerator, IVisualizer, ReportRequest

class AnalyticsReportService:
    """
    Orchestrates the generation of comprehensive analytics reports.
    Decouples report content (DataFrame) from report presentation (Excel/Visuals).
    """
    def __init__(self, report_generator: IReportGenerator, visualizer: IVisualizer):
        self.report_generator = report_generator
        self.visualizer = visualizer

    def create_comprehensive_report(self,
                                    anomalies: Dict[str, pd.DataFrame],
                                    strategy: str,
                                    filepath: str) -> None:
        """
        Generates visuals for the data and produces the final report.
        """
        visuals: Dict[str, io.BytesIO] = {}

        # Generate visuals for each anomaly group
        for v_type, df in anomalies.items():
            if not df.empty:
                # Generate Heatmap
                title = f"{v_type} Performance Heatmap"
                try:
                    visuals[v_type] = self.visualizer.generate_heatmap(df, title)
                except Exception as e:
                    # Log error but continue report generation
                    print(f"Error generating visual for {v_type}: {e}")

        # Create request object
        request = ReportRequest(
            anomalies=anomalies,
            strategy=strategy,
            filepath=filepath
        )

        # Generate Report
        self.report_generator.generate_report(request, visuals)
