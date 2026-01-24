"""
Interfaces and Contracts for the Bachata Brain Breaks Analytics system.
Follows Interface Segregation and Dependency Inversion principles.
"""
from typing import Protocol, Dict, Any
import io
import pandas as pd
from pydantic import BaseModel, ConfigDict

class ReportRequest(BaseModel):
    """
    Encapsulates all data required to generate a report.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    anomalies: Dict[str, pd.DataFrame]
    strategy: str
    filepath: str

class IVisualizer(Protocol):
    """
    Interface for generating visualizations.
    """
    def generate_heatmap(self, data: pd.DataFrame, title: str) -> io.BytesIO:
        """Generates a heatmap/chart and returns the image as bytes."""
        ...

class IReportGenerator(Protocol):
    """
    Interface for report generation.
    """
    def generate_report(self, request: ReportRequest, visuals: Dict[str, io.BytesIO]) -> None:
        """Generates the report with embedded visuals."""
        ...
