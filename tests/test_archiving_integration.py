import pandas as pd
from unittest.mock import Mock
from pathlib import Path

from src.core.models import AnalysisRun
from src.core.repository import JsonLinesRepository
from src.core.reporting import ArchivingReportGenerator
from src.core.interfaces import ReportGenerator


def test_archiving_report_generator_integration(tmp_path: Path) -> None:
    """
    Test that the ArchivingReportGenerator correctly delegates to the inner
    ReportGenerator and accurately persists the AnalysisRun into the
    repository.
    """
    # 1. Setup Mock Inner Generator and temporary Repository
    mock_inner_generator = Mock(spec=ReportGenerator)
    archive_file = tmp_path / "test_archive.jsonl"
    repository = JsonLinesRepository(str(archive_file), AnalysisRun)

    archiving_generator = ArchivingReportGenerator(
        inner=mock_inner_generator,
        repository=repository
    )

    # 2. Setup Test Data
    mock_anomalies = {
        "Shorts": pd.DataFrame({"id": [1, 2, 3]}),
        "Long": pd.DataFrame({"id": [4, 5]})
    }
    mock_strategy = (
        "Test AI generated strategy that is sufficiently long to check if we "
        "can truncate it if we wanted to but it is fine."
    )
    mock_filepath = str(tmp_path / "output_report.xlsx")

    # 3. Execution
    archiving_generator.generate_report(
        anomalies=mock_anomalies,
        strategy=mock_strategy,
        filepath=mock_filepath
    )

    # 4. Verify Delegation
    mock_inner_generator.generate_report.assert_called_once_with(
        mock_anomalies, mock_strategy, mock_filepath
    )

    # 5. Verify Persistence
    assert archive_file.exists(), "Archive file was not created"

    # Retrieve from repository to verify domain model
    saved_runs = repository.get_all()
    assert len(saved_runs) == 1

    run_entity = saved_runs[0]
    assert isinstance(run_entity, AnalysisRun)

    # Verify accurate mapping of domain fields
    assert run_entity.total_anomalies == 5  # 3 Shorts + 2 Longs
    assert run_entity.strategy_preview.startswith("Test AI generated strategy")

    # Optional: Verify truncation if applicable, though we know strategy > 100
    # chars
    assert len(run_entity.strategy_preview) <= 103  # 100 + "..."
