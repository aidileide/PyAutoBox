"""Typer command-line interface for PyAutoBox."""

from __future__ import annotations

import glob
import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from pyautobox import __version__
from pyautobox.config import DEFAULT_IMAGE_QUALITY, DEFAULT_PORT
from pyautobox.core.conversion.audio import read_audio_metadata
from pyautobox.core.conversion.batch import batch_convert
from pyautobox.core.conversion.operations import convert_one
from pyautobox.core.conversion.registry import registry
from pyautobox.core.excel_tools import merge_excel_files
from pyautobox.core.image_tools import compress_image
from pyautobox.core.markdown_tools import markdown_to_pdf
from pyautobox.core.organize_tools import organize_folder, undo_last_organization
from pyautobox.core.pdf_tools import merge_pdfs
from pyautobox.core.rename_tools import execute_renames, plan_renames
from pyautobox.exceptions import PyAutoBoxError

app = typer.Typer(
    name="autobox",
    help="PyAutoBox - Personal Automation Toolbox",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
pdf_app = typer.Typer(help="PDF tools.", no_args_is_help=True)
excel_app = typer.Typer(help="Excel tools.", no_args_is_help=True)
image_app = typer.Typer(help="Image tools.", no_args_is_help=True)
app.add_typer(pdf_app, name="pdf")
app.add_typer(excel_app, name="excel")
app.add_typer(image_app, name="image")


def _fail(error: Exception) -> None:
    typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _overwrite_allowed(output: Path, force: bool) -> bool:
    if not output.exists() or force:
        return force
    return typer.confirm(f"{output} already exists. Overwrite it?")


@pdf_app.command("merge")
def pdf_merge(
    files: Annotated[list[Path], typer.Argument(help="PDF files in merge order.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output PDF path.")],
    force: Annotated[bool, typer.Option("--force", help="Overwrite without asking.")] = False,
) -> None:
    """Merge PDF files in the given order."""
    try:
        if output.exists() and not _overwrite_allowed(output, force):
            raise typer.Abort()
        result = merge_pdfs(files, output, overwrite=output.exists())
        typer.secho(f"Created: {result}", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


@excel_app.command("merge")
def excel_merge(
    files: Annotated[list[Path], typer.Argument(help="Excel files to merge.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output .xlsx path.")],
    sheet: Annotated[str | None, typer.Option("--sheet", help="Worksheet name.")] = None,
    no_source: Annotated[
        bool, typer.Option("--no-source", help="Do not add the _source_file column.")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Overwrite without asking.")] = False,
) -> None:
    """Merge the first or selected worksheets by rows."""
    try:
        if output.exists() and not _overwrite_allowed(output, force):
            raise typer.Abort()
        result = merge_excel_files(
            files,
            output,
            sheet_name=sheet if sheet else 0,
            include_source=not no_source,
            overwrite=output.exists(),
        )
        typer.secho(f"Created: {result}", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


def _expand_image_patterns(patterns: list[str]) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        expanded = str(Path(pattern).expanduser())
        found = [Path(item) for item in glob.glob(expanded)]
        matches.extend(found or [Path(expanded)])
    unique: dict[Path, None] = {}
    for match in matches:
        unique[match] = None
    return list(unique)


@image_app.command("compress")
def image_compress(
    files: Annotated[list[str], typer.Argument(help="Images or wildcard patterns.")],
    quality: Annotated[
        int, typer.Option("--quality", "-q", min=10, max=100, help="Quality from 10 to 100.")
    ] = DEFAULT_IMAGE_QUALITY,
    max_width: Annotated[
        int | None, typer.Option("--max-width", min=1, help="Optional maximum pixel width.")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite generated files.")] = False,
) -> None:
    """Compress one or more JPG, PNG, or WEBP images."""
    try:
        paths = _expand_image_patterns(files)
        if len(paths) == 1:
            outputs = [paths[0].with_name(f"{paths[0].stem}_compressed{paths[0].suffix.lower()}")]
        else:
            parents = {path.parent.resolve(strict=False) for path in paths}
            output_dir = (next(iter(parents)) if len(parents) == 1 else Path.cwd()) / "compressed"
            outputs = [output_dir / path.name for path in paths]

        for source, output in zip(paths, outputs, strict=True):
            result = compress_image(
                source,
                output,
                quality=quality,
                max_width=max_width,
                overwrite=force,
            )
            typer.echo(
                f"{source.name} -> {result.output_path} "
                f"({result.original_size} -> {result.compressed_size} bytes, "
                f"saved {result.saved_percent:.1f}%)"
            )
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("rename")
def rename_command(
    directory: Annotated[Path, typer.Argument(help="Directory containing files to rename.")],
    prefix: Annotated[str, typer.Option("--prefix", help="Prefix for generated names.")] = "",
    suffix: Annotated[str, typer.Option("--suffix", help="Suffix before each extension.")] = "",
    start: Annotated[int, typer.Option("--start", min=0, help="Starting number.")] = 1,
    digits: Annotated[int, typer.Option("--digits", min=1, help="Number padding width.")] = 3,
    replace_old: Annotated[
        str | None, typer.Option("--replace-old", help="Text to replace in existing stems.")
    ] = None,
    replace_new: Annotated[
        str, typer.Option("--replace-new", help="Replacement text for --replace-old.")
    ] = "",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without renaming.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Safely rename files using a collision-proof two-phase operation."""
    try:
        operations = plan_renames(
            directory,
            prefix=prefix,
            suffix=suffix,
            start=start,
            digits=digits,
            replace_old=replace_old,
            replace_new=replace_new,
        )
        if not operations:
            typer.echo("No files need renaming.")
            return
        for operation in operations:
            typer.echo(f"{operation.source.name} -> {operation.target.name}")
        if dry_run:
            typer.secho("Dry run only; no files were changed.", fg=typer.colors.YELLOW)
            return
        if not yes and not typer.confirm(f"Rename {len(operations)} file(s)?"):
            raise typer.Abort()
        execute_renames(operations)
        typer.secho(f"Renamed {len(operations)} file(s).", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("md2pdf")
def md2pdf_command(
    input_file: Annotated[Path, typer.Argument(help="UTF-8 Markdown file.")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output PDF path.")] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite without asking.")] = False,
) -> None:
    """Convert basic Markdown to PDF without a browser dependency."""
    destination = output or input_file.with_suffix(".pdf")
    try:
        if destination.exists() and not _overwrite_allowed(destination, force):
            raise typer.Abort()
        result = markdown_to_pdf(input_file, destination, overwrite=destination.exists())
        typer.secho(f"Created: {result}", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("convert")
def convert_command(
    input_file: Annotated[Path, typer.Argument(help="要转换的文件。")],
    target: Annotated[str, typer.Option("--to", help="目标格式，不含点号。")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    quality: Annotated[int, typer.Option("--quality", min=1, max=100)] = 85,
    max_width: Annotated[int | None, typer.Option("--max-width", min=1)] = None,
    max_height: Annotated[int | None, typer.Option("--max-height", min=1)] = None,
    sheet: Annotated[str | None, typer.Option("--sheet")] = None,
    force: Annotated[bool, typer.Option("--force", help="覆盖已有输出文件。")] = False,
) -> None:
    """转换图片、表格、JSON/YAML、Markdown 或 HTML 文件。"""
    try:
        result = convert_one(
            input_file,
            target,
            output,
            overwrite=force,
            options={
                "quality": quality,
                "max_width": max_width,
                "max_height": max_height,
                "sheet": sheet,
                "pretty": True,
                "standalone": True,
            },
        )
        typer.secho(f"已生成：{result}", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("batch-convert")
def batch_convert_command(
    input_dir: Annotated[Path, typer.Argument(help="输入目录。")],
    source: Annotated[str, typer.Option("--from", help="源格式。")],
    target: Annotated[str, typer.Option("--to", help="目标格式。")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    recursive: Annotated[bool, typer.Option("--recursive")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """批量转换目录中的同类文件。"""
    try:
        results = batch_convert(
            input_dir,
            source,
            target,
            output,
            recursive=recursive,
            overwrite=force,
        )
        if not results:
            typer.secho("没有找到可转换文件。", fg=typer.colors.YELLOW)
        for result in results:
            typer.echo(str(result))
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("audio-info")
def audio_info_command(
    input_file: Annotated[Path, typer.Argument(help="MP3、FLAC、M4A 或 OGG 文件。")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """读取音频标签与技术信息。"""
    try:
        text = json.dumps(read_audio_metadata(input_file), ensure_ascii=False, indent=2)
        if output:
            output.write_text(text + "\n", encoding="utf-8")
            typer.secho(f"已生成：{output}", fg=typer.colors.GREEN)
        else:
            typer.echo(text)
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("formats")
def formats_command() -> None:
    """列出所有支持的格式转换。"""
    for category, sources in registry.list_formats().items():
        typer.secho(f"\n{category}", bold=True)
        for source, targets in sources.items():
            typer.echo(f"  {source:<6} → {', '.join(targets)}")


@app.command("clean-desktop")
def clean_desktop(
    path: Annotated[
        Path | None, typer.Option("--path", help="Folder to organize; defaults to Desktop.")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--apply", help="Preview by default; use --apply to move files."),
    ] = True,
    undo: Annotated[bool, typer.Option("--undo", help="Undo the latest completed run.")] = False,
) -> None:
    """Move files into category folders; never delete files."""
    target = (path or (Path.home() / "Desktop")).expanduser()
    try:
        if undo:
            operations = undo_last_organization(target)
            for operation in operations:
                typer.echo(f"Restored: {operation.source.name} -> {operation.target.name}")
            typer.secho(f"Restored {len(operations)} file(s).", fg=typer.colors.GREEN)
            return
        operations = organize_folder(target, dry_run=dry_run)
        for operation in operations:
            typer.echo(
                f"{operation.source.name} -> "
                f"{operation.target.relative_to(target)}"
            )
        if dry_run:
            typer.secho("Dry run only. Re-run with --apply to move files.", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"Organized {len(operations)} file(s).", fg=typer.colors.GREEN)
    except PyAutoBoxError as exc:
        _fail(exc)


@app.command("serve")
def serve(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = DEFAULT_PORT,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
) -> None:
    """Start the local PyAutoBox Web interface."""
    import uvicorn

    typer.echo(f"PyAutoBox is running at http://{host}:{port}")
    uvicorn.run("pyautobox.main:app", host=host, port=port, log_level="info")


@app.command("version")
def version() -> None:
    """Show the installed PyAutoBox version."""
    typer.echo(f"PyAutoBox {__version__}")


def run() -> None:
    """Console-script entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app()


if __name__ == "__main__":
    run()
