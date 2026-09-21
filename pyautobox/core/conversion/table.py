"""CSV, Excel, and record-oriented JSON conversions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from pyautobox.core.conversion.base import Converter, format_from_path
from pyautobox.exceptions import InvalidFileError

logger = logging.getLogger(__name__)


class TableConverter(Converter):
    """Convert tabular files through a validated pandas DataFrame."""

    category = "Tables"
    source_formats = frozenset({"csv", "xlsx", "json"})
    target_formats = frozenset({"csv", "xlsx", "json"})

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Convert a tabular document while preserving Unicode text."""
        options = options or {}
        frame = self.read(input_path, options.get("sheet"))
        target = format_from_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target == "csv":
                frame.to_csv(output_path, index=False, encoding="utf-8-sig")
            elif target == "xlsx":
                frame.to_excel(output_path, index=False, engine="openpyxl")
            elif target == "json":
                orient = str(options.get("json_orient", "records"))
                if orient != "records":
                    raise InvalidFileError("表格 JSON 目前只支持 records 数组格式。")
                frame.to_json(output_path, orient="records", force_ascii=False, indent=2)
            else:
                raise InvalidFileError(f"不支持的表格输出格式：{target}")
        except (OSError, ValueError, TypeError) as exc:
            if isinstance(exc, InvalidFileError):
                raise
            raise InvalidFileError(f"无法写入 {target.upper()} 表格。") from exc
        return output_path

    def read(self, input_path: Path, sheet: object = None) -> pd.DataFrame:
        """Read and validate one supported table format."""
        source = format_from_path(input_path)
        try:
            if source == "csv":
                return self._read_csv(input_path)
            if source == "xlsx":
                book = pd.ExcelFile(input_path, engine="openpyxl")
                selected = str(sheet) if sheet else book.sheet_names[0]
                if selected not in book.sheet_names:
                    raise InvalidFileError(f"找不到工作表：{selected}")
                if len(book.sheet_names) > 1 and not sheet:
                    logger.warning(
                        "Workbook has multiple sheets; using %s. Use --sheet to choose another.",
                        selected,
                    )
                return pd.read_excel(book, sheet_name=selected)
            if source == "json":
                data = json.loads(input_path.read_text(encoding="utf-8-sig"))
                if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                    raise InvalidFileError("表格 JSON 必须是对象数组。")
                return pd.DataFrame.from_records(data)
        except UnicodeDecodeError as exc:
            raise InvalidFileError("CSV 必须使用 UTF-8 或 UTF-8-SIG 编码。") from exc
        except json.JSONDecodeError as exc:
            raise InvalidFileError(
                f"JSON 无效：第 {exc.lineno} 行，第 {exc.colno} 列：{exc.msg}"
            ) from exc
        except (OSError, ValueError, KeyError) as exc:
            if isinstance(exc, InvalidFileError):
                raise
            raise InvalidFileError("电子表格文件无效。") from exc
        raise InvalidFileError(f"不支持的表格输入格式：{source}")

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        last_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise InvalidFileError("CSV 文件无效。")

