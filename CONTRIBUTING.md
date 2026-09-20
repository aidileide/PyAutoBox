# Contributing to PyAutoBox

感谢你愿意改进 PyAutoBox。

## 开发流程

1. Fork 项目并从 `main` 创建功能分支。
2. 使用 Python 3.11+ 创建虚拟环境。
3. 运行 `python -m pip install -e ".[dev]"`。
4. 修改业务逻辑时，请放在 `pyautobox/core/`；CLI 与 Web 只负责输入输出适配。
5. 为新增行为补充使用 `tmp_path` 的测试。
6. 提交前运行：

```bash
python -m pytest
python -m ruff check .
```

## Pull Request

- 保持改动聚焦，说明问题、方案和测试结果。
- 不要提交真实私人文件、凭据或包含敏感信息的日志。
- 新依赖必须有明确用途，并优先选择跨平台、安装简单的方案。
- 涉及文件移动或覆盖时，必须提供冲突检测和可恢复策略。

提交代码即表示你同意按本项目的 MIT License 发布贡献。
