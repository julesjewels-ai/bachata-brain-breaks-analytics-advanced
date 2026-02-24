import pytest
import io
import pandas as pd
from rich.console import Console
from src.core.ui import RichConsoleUI

def test_integration_console_output():
    # Use record=True to capture output
    console = Console(record=True, force_terminal=True, width=80)
    ui = RichConsoleUI(console=console)

    ui.display_header("Integration Test")
    ui.display_section("Section 1")
    ui.display_status("Status: Running")

    # Export plain text
    output = console.export_text()

    assert "Integration Test" in output
    assert "Section 1" in output
    assert "Status: Running" in output

def test_integration_table_rendering():
    console = Console(record=True, force_terminal=True, width=80)
    ui = RichConsoleUI(console=console)

    df = pd.DataFrame({
        'Video Title': ['Video A', 'Video B'],
        'Views': [1000, 2000]
    })

    ui.display_table(df, title="Top Videos")

    output = console.export_text()

    assert "Top Videos" in output
    assert "Video A" in output
    assert "Video B" in output
    assert "1000" in output
    assert "2000" in output

@pytest.mark.asyncio
async def test_integration_stream():
    console = Console(record=True, force_terminal=True, width=80)
    ui = RichConsoleUI(console=console)

    async def stream_gen():
        yield "Part 1 "
        yield "Part 2"

    await ui.display_stream(stream_gen())

    output = console.export_text()
    assert "Part 1 Part 2" in output
