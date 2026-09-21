<p align="center">
  <img src="docs/logo-placeholder.svg" width="160" alt="PyAutoBox logo placeholder">
</p>

<h1 align="center">PyAutoBox</h1>

<p align="center"><strong>Simple tools. Less repetitive work.</strong></p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <a href="https://github.com/aidileide/PyAutoBox/releases"><img alt="Version" src="https://img.shields.io/badge/version-0.2.1-4f46e5"></a>
  <a href="https://github.com/aidileide/PyAutoBox/actions"><img alt="Tests" src="https://github.com/aidileide/PyAutoBox/actions/workflows/tests.yml/badge.svg"></a>
  <a href="https://pypi.org/project/pyautobox/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pyautobox?label=PyPI"></a>
  <a href="https://github.com/aidileide/PyAutoBox/stargazers"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/aidileide/PyAutoBox?style=flat"></a>
</p>

PyAutoBox 是一个轻量、简单、实用的个人自动化工具箱。它同时提供可复用的 Python
核心模块、Typer 命令行界面，以及仅在本机运行的 FastAPI Web 图形界面。

CLI 和 Web 不重复实现业务逻辑：两者都调用 `pyautobox/core/` 中的同一组函数。

## 功能

- PDF 合并：按输入顺序合并任意数量 PDF。
- Excel 合并：按行合并 `.xlsx` / `.xls`，自动取列并集并可记录来源文件。
- 图片压缩：支持 JPG、JPEG、PNG、WEBP，处理 EXIF 方向、透明背景和宽度限制。
- 批量重命名：先预览、检测冲突，再通过两阶段重命名避免名称链冲突。
- Markdown 转 PDF：支持标题、文本、粗体、斜体、列表、代码块、引用和链接文本。
- 文件夹整理：只移动、不删除，默认 dry-run，并支持撤销最近一次整理。
- 万能格式转换：图片、CSV/XLSX/JSON、JSON/YAML、Markdown/HTML/TXT 互转。
- 音频信息查看：读取 MP3、FLAC、M4A、OGG 的标签与技术参数。
- 批量转换：多文件 Web 打包下载，CLI 支持目录递归转换。
- 本地 Web UI：拖拽上传、异步处理、结果下载、响应式布局。

## Web UI

<p align="center">
  <img src="docs/web-ui.png" width="820" alt="PyAutoBox 中文 Web UI">
</p>

## 安装

要求 Python 3.11 或更高版本。

```bash
pip install pyautobox
```

从源码安装开发版本：

```bash
git clone https://github.com/aidileide/PyAutoBox.git
cd PyAutoBox
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS / Linux：

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 快速开始

```bash
autobox --help
autobox version
autobox pdf merge a.pdf b.pdf -o merged.pdf
autobox image compress photo.jpg --quality 75 --max-width 1920
autobox convert data.json --to yaml
autobox batch-convert ./images --from png --to webp
autobox serve
```

### 格式转换

```bash
autobox formats
autobox convert photo.png --to webp --quality 82
autobox convert report.csv --to xlsx
autobox convert config.json --to yaml
autobox convert README.md --to html
autobox batch-convert ./photos --from png --to jpg --recursive
autobox audio-info song.mp3 --output metadata.json
```

输出文件已存在时自动生成不冲突的文件名；使用 `--force` 才会覆盖。Web 首页也提供同一套转换能力。

打开浏览器访问 <http://127.0.0.1:8000>。

## CLI 使用示例

### PDF 合并

```bash
autobox pdf merge a.pdf b.pdf c.pdf -o merged.pdf
autobox pdf merge a.pdf b.pdf -o merged.pdf --force
```

输出文件已存在时，CLI 默认询问是否覆盖；`--force` 可跳过询问。

### Excel 合并

```bash
autobox excel merge january.xlsx february.xlsx -o merged.xlsx
autobox excel merge a.xlsx b.xls -o merged.xlsx --sheet Data
autobox excel merge a.xlsx b.xlsx -o merged.xlsx --no-source
```

默认读取第一个工作表，并添加 `_source_file` 列。不同输入表的列名不一致时，会保留所有列，
缺失单元格为空。

### 图片压缩

```bash
autobox image compress photo.jpg
autobox image compress "*.jpg" --quality 75 --max-width 1920
```

单张图片默认输出为 `photo_compressed.jpg`；批量处理会在 `compressed/` 中创建结果。
在 Windows 命令提示符或 PowerShell 中，可以保留通配符引号，由 PyAutoBox 自行展开。

### 批量重命名

```bash
autobox rename ./photos --prefix vacation_ --dry-run
autobox rename ./photos --prefix vacation_
autobox rename ./photos --replace-old "IMG_" --replace-new "Tokyo_"
```

执行前总会打印完整预览，并要求确认（可用 `--yes` 跳过）。核心模块先将所有源文件重命名为
随机临时名，再统一改为目标名，因此 `A → B、B → C` 不会互相覆盖。

### Markdown 转 PDF

```bash
autobox md2pdf README.md -o README.pdf
```

PyAutoBox 使用纯 Python 的 ReportLab 直接排版 PDF，不要求安装 Chrome、wkhtmltopdf 或其他
系统程序。中文优先使用 ReportLab 的 `STSong-Light` CID 字体；如果当前运行环境无法注册该
字体，会记录清晰警告并回退到 Helvetica，而不会导致程序崩溃。第一版定位为实用的基础
Markdown 排版，不等同于浏览器级 CSS 渲染。

### 文件夹自动整理

```bash
autobox clean-desktop
autobox clean-desktop --path ~/Downloads
autobox clean-desktop --path ~/Downloads --apply
autobox clean-desktop --path ~/Downloads --undo
```

安全规则：

- 默认只预览；必须显式使用 `--apply` 才会移动文件。
- 只移动目录顶层的文件，绝不删除文件。
- 同名目标自动变成 `file_1.ext`、`file_2.ext`，不会覆盖。
- 每次实际整理都会在目标目录写入 `.pyautobox_history.json`。
- `--undo` 恢复最近一次尚未撤销的整理；若原位置已被占用则停止并报错。

## Web 使用方法

```bash
autobox serve
autobox serve --port 8080
```

Web UI 提供 PDF 合并、Excel 合并、图片压缩、Markdown 转 PDF，以及图片、表格、结构化
数据、文档和批量格式转换。批量重命名和文件整理只在 CLI 中开放；Web 不接受服务器路径，
也不能浏览任意本地文件系统。

上传安全设计：

- 上传使用随机临时目录和随机存储名，不信任客户端文件名。
- 对原始文件名执行 basename 过滤，并限定每个工具的扩展名。
- 默认单文件上限为 100 MB。
- 下载响应发送完成后删除整个任务临时目录。
- Web 不执行 shell、Python 代码、`eval()` 或 `exec()`。

可用环境变量：

| 变量 | 默认值 | 说明 |
| --- | ---: | --- |
| `PYAUTOBOX_MAX_UPLOAD_MB` | `100` | Web 单文件上传上限（MB） |
| `PYAUTOBOX_MAX_BATCH_FILES` | `100` | Web 单次批处理文件数上限 |
| `PYAUTOBOX_PORT` | `8000` | `autobox serve` 默认端口 |

## Python API

核心函数也可以直接在 Python 中使用：

```python
from pathlib import Path

from pyautobox.core.pdf_tools import merge_pdfs

merge_pdfs(
    [Path("a.pdf"), Path("b.pdf")],
    Path("merged.pdf"),
)
```

## 开发

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

GitHub Actions 会在 Python 3.11、3.12、3.13 上执行相同的测试与 Ruff 检查。

## 项目结构

```text
PyAutoBox/
├── pyproject.toml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── pyautobox/
│   ├── cli.py
│   ├── config.py
│   ├── exceptions.py
│   ├── core/                # CLI 与 Web 共用的业务逻辑
│   └── web/
│       ├── app.py
│       ├── routes/          # HTML 页面与 /api 路由
│       ├── templates/       # Jinja2 模板
│       └── static/          # 原生 CSS / JavaScript
├── tests/
└── .github/workflows/tests.yml
```

## Roadmap

- 增加更丰富的 Markdown 表格与语法支持。
- 增加图片输出格式与元数据保留选项。
- 增加文件整理规则配置文件。
- 发布 PyPI 正式包与真实 Web UI 截图。

## Contributing

欢迎提交 Issue 和 Pull Request。开始前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

本项目采用 [MIT License](LICENSE)。
