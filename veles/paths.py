"""Where VELES finds things, in development and as a frozen .exe. No Qt.

Three locations that are the same folder in development but separate in an .exe:
  resources      stylesheet + icons, bundled inside the app          -> resource()
  repo root      config/, scripts, logs/, the dependency map          -> repo_root()
  script python  the `pipeline` conda env that runs the scripts       -> pipeline_python()
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType

PACKAGE_DIR = Path(__file__).resolve().parent
HIERARCHY_FILE = "RCP_analysis/python/functions/pipeline_hierarchy.py"
PARAMS_LOADING_FILE = "RCP_analysis/python/functions/params_loading.py"
CONDA_ENV = "pipeline"

_chosen: dict[str, Path] = {}


class LocationNotFound(Exception):
    def __init__(self, what: str, tried: list[Path]):
        self.what = what
        self.tried = tried
        super().__init__(f"Could not find the {what}. Tried: " + ", ".join(str(p) for p in tried))


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource(name: str) -> Path:
    base = Path(sys._MEIPASS) / "veles" if is_frozen() else PACKAGE_DIR
    return base / name


def is_repo(path: Path) -> bool:
    return (path / HIERARCHY_FILE).is_file() and (path / "config" / "params.yaml").is_file()


def is_python(path: Path) -> bool:
    return path.is_file() and path.name.lower().startswith("python")


def repo_candidates() -> list[Path]:
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        return [exe_dir, exe_dir.parent]
    return [PACKAGE_DIR.parent]


def python_candidates() -> list[Path]:
    if not is_frozen():
        return [Path(sys.executable)]
    return [Path.home() / base / "envs" / CONDA_ENV / "python.exe" for base in ("miniconda3", "anaconda3", "mambaforge")]


def use_locations(repo: Path | None = None, python: Path | None = None) -> None:
    """Pin the locations (from saved settings or the Locate dialog). None leaves that one to be guessed."""
    for key, value in (("repo", repo), ("python", python)):
        if value is None:
            _chosen.pop(key, None)
        else:
            _chosen[key] = Path(value)
    hierarchy.cache_clear()
    params_loading.cache_clear()


def repo_root() -> Path:
    if "repo" in _chosen:
        return _chosen["repo"]
    candidates = repo_candidates()
    for path in candidates:
        if is_repo(path):
            return path
    raise LocationNotFound("RCP_analysis repo", candidates)


def pipeline_python() -> Path:
    if "python" in _chosen:
        return _chosen["python"]
    candidates = python_candidates()
    for path in candidates:
        if is_python(path):
            return path
    raise LocationNotFound(f"'{CONDA_ENV}' conda env python", candidates)


def _load_repo_file(relative: str, module_name: str) -> ModuleType:
    """Import one repo file directly, skipping RCP_analysis/__init__.py (which pulls in pandas, scipy, ...)."""
    path = repo_root() / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Can't load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # dataclasses in the file look themselves up here
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def hierarchy() -> ModuleType:
    """The repo's pipeline_hierarchy.py: COLUMN_DEPENDENCIES, SCRIPT_STATUS_COLUMNS, parse_status_timestamp, ..."""
    return _load_repo_file(HIERARCHY_FILE, "veles_repo_pipeline_hierarchy")


@lru_cache(maxsize=None)
def params_loading() -> ModuleType:
    return _load_repo_file(PARAMS_LOADING_FILE, "veles_repo_params_loading")
