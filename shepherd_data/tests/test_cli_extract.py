from pathlib import Path

from click.testing import CliRunner

from shepherd_data.cli import cli


def test_cli_extract_file_full(data_h5: Path) -> None:
    res = CliRunner().invoke(
        cli,
        [
            "--verbose",
            "extract",
            # "--start", "1",
            # "--end", "5",
            "--ds-factor",
            "100",
            "--separator",
            ",",
            "--raw",
            str(data_h5),
        ],
    )
    assert res.exit_code == 0
    assert data_h5.with_suffix(".downsampled_x100.h5").exists()
    assert data_h5.with_suffix(".downsampled_x100.data.csv").exists()


def test_cli_extract_file_short(data_h5: Path) -> None:
    res = CliRunner().invoke(cli, ["-v", "extract", "-f", "200", "--separator", ";", str(data_h5)])
    assert res.exit_code == 0
    assert data_h5.with_suffix(".downsampled_x200.h5").exists()
    assert data_h5.with_suffix(".downsampled_x200.data.csv").exists()


def test_cli_extract_file_min(data_h5: Path) -> None:
    res = CliRunner().invoke(cli, ["-v", "extract", str(data_h5)])
    assert res.exit_code == 0
    assert data_h5.with_suffix(".downsampled_x1000.h5").exists()
    assert data_h5.with_suffix(".downsampled_x1000.data.csv").exists()


def test_cli_extract_dir_full(data_h5: Path) -> None:
    print(data_h5.parent)
    print(data_h5.parent.is_dir())
    res = CliRunner().invoke(
        cli,
        [
            "--verbose",
            "extract",
            "--ds-factor",
            "2000",
            "--separator",
            ";",
            str(data_h5.parent),
        ],
    )
    assert res.exit_code == 0
    assert data_h5.with_suffix(".downsampled_x2000.h5").exists()
    assert data_h5.with_suffix(".downsampled_x2000.data.csv").exists()
