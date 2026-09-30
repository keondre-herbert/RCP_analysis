import subprocess
import sys
from pathlib import Path

import pytest

from veles import paths


@pytest.fixture(autouse=True)
def reset_locations():
    yield
    paths.use_locations()


def make_fake_repo(root: Path, deps: str) -> Path:
    (root / "config").mkdir(parents=True)
    (root / "config" / "params.yaml").write_text("paths: {data_root: x}\n")
    hierarchy = root / paths.HIERARCHY_FILE
    hierarchy.parent.mkdir(parents=True)
    hierarchy.write_text(f"COLUMN_DEPENDENCIES = {deps}\n")
    return root


def fake_exe(monkeypatch, exe: Path, bundle: Path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))


def test_dev_repo_root_is_this_repo():
    assert paths.repo_root() == Path(__file__).resolve().parent.parent
    assert paths.is_repo(paths.repo_root())


def test_hierarchy_is_loaded_from_the_repo_file():
    assert "extract_peri" in paths.hierarchy().COLUMN_DEPENDENCIES
    assert paths.hierarchy() is paths.hierarchy()  # loaded once


def test_hierarchy_follows_the_chosen_repo(tmp_path):
    paths.use_locations(repo=make_fake_repo(tmp_path, '{"A": [], "B": ["A"]}'))
    assert paths.hierarchy().COLUMN_DEPENDENCIES == {"A": [], "B": ["A"]}


def test_importing_veles_does_not_load_the_science_stack():
    code = "import sys, veles.data, veles.planner; print(sorted({'pandas', 'scipy', 'RCP_analysis'} & set(sys.modules)))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=paths.repo_root(), check=True)
    assert out.stdout.strip() == "[]"


def test_frozen_resources_come_from_the_bundle(monkeypatch, tmp_path):
    fake_exe(monkeypatch, tmp_path / "VELES" / "VELES.exe", tmp_path / "bundle")
    assert paths.resource("veles.qss") == tmp_path / "bundle" / "veles" / "veles.qss"


def test_frozen_repo_is_found_next_to_or_above_the_exe(monkeypatch, tmp_path):
    repo = make_fake_repo(tmp_path / "RCP_analysis", "{}")
    fake_exe(monkeypatch, repo / "dist" / "VELES.exe", tmp_path / "bundle")
    assert paths.repo_root() == repo


def test_frozen_repo_not_found_lists_what_was_tried(monkeypatch, tmp_path):
    fake_exe(monkeypatch, tmp_path / "Desktop" / "VELES.exe", tmp_path / "bundle")
    with pytest.raises(paths.LocationNotFound) as err:
        paths.repo_root()
    assert err.value.tried == [tmp_path / "Desktop", tmp_path]


def test_frozen_python_never_uses_the_exe(monkeypatch, tmp_path):
    fake_exe(monkeypatch, tmp_path / "VELES.exe", tmp_path / "bundle")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    python = tmp_path / "home" / "miniconda3" / "envs" / "pipeline" / "python.exe"
    with pytest.raises(paths.LocationNotFound):
        paths.pipeline_python()
    python.parent.mkdir(parents=True)
    python.touch()
    assert paths.pipeline_python() == python


def test_chosen_locations_win_over_guesses(tmp_path):
    python = tmp_path / "python.exe"
    paths.use_locations(python=python)
    assert paths.pipeline_python() == python
