import argparse
from pathlib import Path

import pytest

from tracechain.cli import cmd_init


def test_init_creates_files(tmp_path):
    args = argparse.Namespace(directory=str(tmp_path / "proj"), overwrite=False)
    rc = cmd_init(args)
    assert rc == 0
    assert (tmp_path / "proj" / ".env").exists()
    assert (tmp_path / "proj" / "docker-compose.yml").exists()
    assert (tmp_path / "proj" / "pipeline.py").exists()


def test_init_current_dir(tmp_path):
    args = argparse.Namespace(directory=str(tmp_path), overwrite=False)
    rc = cmd_init(args)
    assert rc == 0
    assert (tmp_path / "pipeline.py").read_text(encoding="utf-8").startswith('"""Starter')


def test_init_no_overwrite(tmp_path, capsys):
    sentinel = tmp_path / ".env"
    sentinel.write_text("original", encoding="utf-8")
    args = argparse.Namespace(directory=str(tmp_path), overwrite=False)
    cmd_init(args)
    assert sentinel.read_text(encoding="utf-8") == "original"
    out = capsys.readouterr().out
    assert "skip" in out


def test_init_overwrite(tmp_path):
    sentinel = tmp_path / ".env"
    sentinel.write_text("original", encoding="utf-8")
    args = argparse.Namespace(directory=str(tmp_path), overwrite=True)
    cmd_init(args)
    assert sentinel.read_text(encoding="utf-8") != "original"


def test_init_docker_compose_has_services(tmp_path):
    args = argparse.Namespace(directory=str(tmp_path), overwrite=False)
    cmd_init(args)
    compose = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert "backend" in compose
    assert "dashboard" in compose
    assert "8000:8000" in compose
