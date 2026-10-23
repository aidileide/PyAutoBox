# PyAutoBox

English | [简体中文](README.md)

A local automation toolbox with a shared Python core, Typer CLI, and FastAPI Web
UI. Merge PDFs and spreadsheets, compress images, convert common file formats,
rename files with a preview, and organize folders with undo history.

![PyAutoBox local Web UI](docs/web-ui.png)

## Install from this repository

Requires Python 3.11+ and Git:

```bash
python -m pip install "git+https://github.com/aidileide/PyAutoBox.git"
autobox version
```

This project is not yet published on PyPI. Use this repository URL rather than
`pip install pyautobox`. For reproducible installs, append
`@<reviewed-commit-sha>` to the Git URL.

## Quick start

```bash
autobox --help
autobox pdf merge first.pdf second.pdf -o merged.pdf
autobox image compress photo.jpg --quality 75 --max-width 1920
autobox convert data.json --to yaml
autobox batch-convert ./images --from png --to webp
autobox serve
```

Open `http://127.0.0.1:8000` for the local Web UI. Uploads are processed locally in
temporary task directories. File renaming and folder organization are CLI-only.

Preview file operations before applying them:

```bash
autobox rename ./photos --prefix holiday_ --dry-run
autobox clean-desktop --path ./downloads
autobox clean-desktop --path ./downloads --apply
autobox clean-desktop --path ./downloads --undo
```

Folder organization defaults to a dry run and records actual moves for undo.
Malformed undo history is rejected before files move. Existing destinations are
preserved unless an operation explicitly supports and receives an overwrite flag.

Ordinary audio conversion requires FFmpeg. Some proprietary music containers also
require keys already stored by the local client; see the Chinese guide for supported
formats and limitations. Markdown-to-PDF supports basic Markdown with ReportLab.

## Develop and validate

```bash
git clone https://github.com/aidileide/PyAutoBox.git
cd PyAutoBox
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Then install and run checks:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m build
python -m twine check dist/*
```

CI covers Python 3.11–3.13 on Windows and Linux. A separate job installs the wheel
outside the source checkout and checks the CLI, templates, static assets, and
third-party notices.

Changes to business behavior belong in `pyautobox/core/`; CLI and Web share that
implementation. See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md),
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and the [MIT license](LICENSE).
