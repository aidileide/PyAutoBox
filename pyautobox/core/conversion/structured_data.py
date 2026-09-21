"""JSON and YAML conversions using safe parsers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pyautobox.core.conversion.base import Converter, format_from_path
from pyautobox.exceptions import InvalidFileError


class StructuredDataConverter(Converter):
    """Convert structured data without executing YAML constructors."""

    category = "Structured Data"
    source_formats = frozenset({"json", "yaml"})
    target_formats = frozenset({"json", "yaml"})

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Convert JSON/YAML and report parser positions when available."""
        options = options or {}
        source = format_from_path(input_path)
        target = format_from_path(output_path)
        try:
            text = input_path.read_text(encoding="utf-8-sig")
            data = json.loads(text) if source == "json" else yaml.safe_load(text)
        except json.JSONDecodeError as exc:
            raise InvalidFileError(
                f"{input_path.name} 不是有效的 JSON：第 {exc.lineno} 行，第 {exc.colno} 列。"
            ) from exc
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f"第 {mark.line + 1} 行，第 {mark.column + 1} 列" if mark else "未知位置"
            raise InvalidFileError(f"{input_path.name} 不是有效的 YAML：{where}。") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidFileError(f"无法以 UTF-8 文本读取 {input_path.name}。") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if target == "json":
            indent = 2 if options.get("pretty", True) else None
            output_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8",
            )
        else:
            output_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        return output_path

