from typer.testing import CliRunner

from pyautobox.cli import app

runner = CliRunner()


def test_cli_help_lists_expected_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["pdf", "excel", "image", "rename", "md2pdf", "clean-desktop", "serve"]:
        assert command in result.stdout


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "PyAutoBox 0.2.0" in result.stdout
