from pathlib import Path

import pandas as pd

from pyautobox.core.excel_tools import merge_excel_files


def test_merge_excel_uses_union_and_tracks_source(tmp_path: Path) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    output = tmp_path / "merged.xlsx"
    pd.DataFrame({"name": ["A"], "value": [1]}).to_excel(first, index=False)
    pd.DataFrame({"name": ["B"], "note": ["new"]}).to_excel(second, index=False)

    merge_excel_files([first, second], output)
    merged = pd.read_excel(output)

    assert len(merged) == 2
    assert set(merged.columns) == {"name", "value", "note", "_source_file"}
    assert merged["_source_file"].tolist() == ["first.xlsx", "second.xlsx"]
