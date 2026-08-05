"""
Generic Data Export Layer for Bachata Brain Breaks Analytics.
Provides a flexible, decoupled mechanism to persist raw domain models.
"""
import json
import logging
from typing import Protocol, TypeVar, Generic, List, Sequence
from pydantic import BaseModel
import pandas as pd
from src.core.interfaces import DataIngestionService

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Domain-specific exception for data export failures."""
    pass


T = TypeVar('T', bound=BaseModel)
T_contra = TypeVar('T_contra', bound=BaseModel, contravariant=True)


class DataExporter(Protocol[T_contra]):
    """
    Protocol defining the contract for generic data export.
    """
    def export_batch(self, items: Sequence[T_contra], filepath: str) -> None:
        """
        Exports a batch of strongly typed items.

        Args:
            items: A sequence of domain models to export.
            filepath: Destination file path.
        """
        ...


class JsonLinesExporter(Generic[T]):
    """
    Concrete DataExporter implementation that persists data to a JSONL file.
    Follows the Unit of Work/Repository pattern for decoupled persistence.
    """
    def export_batch(self, items: Sequence[T], filepath: str) -> None:
        if '..' in filepath or not filepath.endswith('.jsonl'):
            raise ExportError(
                f"Invalid or unsafe export path: {filepath}. "
                "Must be a local .jsonl file."
            )

        try:
            with open(filepath, 'w') as f:
                for item in items:
                    f.write(item.model_dump_json() + '\n')
            logger.info("Successfully exported %d items to %s", len(items), filepath)
        except Exception as e:
            logger.error("Failed to export items to %s: %s", filepath, e)
            raise ExportError(f"Export failed: {e}") from e


class ExportingDataIngestionService(Generic[T]):
    """
    Decorator for DataIngestionService that seamlessly intercepts the ingested
    DataFrame, converts it back to domain models, and exports it using a DataExporter.
    Adheres to the Open/Closed Principle by adding behavior via composition.
    """
    def __init__(
        self,
        inner: DataIngestionService,
        exporter: DataExporter[T],
        model_class: type[T],
        export_filepath: str
    ):
        self._inner = inner
        self._exporter = exporter
        self._model_class = model_class
        self._export_filepath = export_filepath

    async def ingest_data(self) -> pd.DataFrame:
        """
        Delegates to the inner ingestion service and exports the result.
        Failures in export do not disrupt the main ingestion flow.
        """
        df = await self._inner.ingest_data()

        try:
            # Map DataFrame rows back to domain models for strictly typed export
            items = [
                self._model_class(**record)
                for record in df.to_dict(orient='records')
            ]
            self._exporter.export_batch(items, self._export_filepath)
        except Exception as e:
            # Soft fail on backup
            logger.warning("Data export step failed (non-fatal): %s", e)

        return df
