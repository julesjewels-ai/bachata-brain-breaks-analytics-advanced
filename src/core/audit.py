"""
Audit module for tracking system actions and states.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Generic, Protocol, TypeVar

import pandas as pd
from pydantic import BaseModel, Field

from src.core.interfaces import DataIngestionService

logger = logging.getLogger(__name__)

class AuditError(Exception):
    """Custom exception for audit-related errors."""


class AuditEvent(BaseModel):
    """Structured audit data."""
    action: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


T = TypeVar('T', contravariant=True)


class Repository(Protocol, Generic[T]):
    """Generic repository protocol."""
    def save(self, item: T) -> None:
        """Saves an item."""
        ...


class AuditService(Protocol):
    """Protocol for recording audit events."""
    def record(self, event: AuditEvent) -> None:
        """Records an audit event."""
        ...


class AuditUnitOfWork(Protocol):
    """Unit of Work for managing audit persistence."""
    def __enter__(self) -> AuditUnitOfWork:
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        ...

    @property
    def audits(self) -> Repository[AuditEvent]:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class FileAuditRepository(Repository[AuditEvent]):
    """File-based implementation of an audit repository."""
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._items: list[AuditEvent] = []

    def save(self, item: AuditEvent) -> None:
        self._items.append(item)

    def flush(self) -> None:
        """Writes items to file."""
        if not self._items:
            return
        try:
            with open(self.filepath, 'a', encoding="utf-8") as f:
                for item in self._items:
                    event_dict = item.model_dump()
                    event_dict['timestamp'] = event_dict['timestamp'].isoformat()
                    f.write(json.dumps(event_dict) + "\n")
            self._items.clear()
        except Exception as e:
            logger.error("Failed to write audit to %s: %s", self.filepath, e)
            raise AuditError(f"Audit persistence error: {e}") from e


class FileAuditUnitOfWork(AuditUnitOfWork):
    """File-based implementation of AuditUnitOfWork."""
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._repository: FileAuditRepository | None = None

    def __enter__(self) -> FileAuditUnitOfWork:
        self._repository = FileAuditRepository(self.filepath)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @property
    def audits(self) -> Repository[AuditEvent]:
        if self._repository is None:
            raise AuditError("Unit of Work not initialized")
        return self._repository

    def commit(self) -> None:
        if self._repository:
            self._repository.flush()

    def rollback(self) -> None:
        if self._repository:
            self._repository._items.clear()


class StandardAuditService(AuditService):
    """Standard implementation of AuditService using a Unit of Work."""
    def __init__(self, uow: AuditUnitOfWork) -> None:
        self.uow = uow

    def record(self, event: AuditEvent) -> None:
        with self.uow as uow:
            uow.audits.save(event)


class AuditedDataIngestionService(DataIngestionService):
    """Decorator to add auditing to DataIngestionService."""
    def __init__(self, inner: DataIngestionService, audit_service: AuditService) -> None:
        self.inner = inner
        self.audit_service = audit_service

    async def ingest_data(self) -> pd.DataFrame:
        self.audit_service.record(AuditEvent(
            action="ingest_data",
            status="started"
        ))
        try:
            result = await self.inner.ingest_data()
            self.audit_service.record(AuditEvent(
                action="ingest_data",
                status="completed",
                details={"row_count": len(result)}
            ))
            return result
        except BaseException as e:
            self.audit_service.record(AuditEvent(
                action="ingest_data",
                status="failed",
                details={"error": type(e).__name__}
            ))
            raise
