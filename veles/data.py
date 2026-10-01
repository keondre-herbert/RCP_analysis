from __future__ import annotations

import csv
import hashlib
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from veles import paths

STATUS_CSV_NAME = "data_status_reaching.csv"
FINGERPRINT_NAME = "manual_trial_remove.sha256"

CHIP_COLUMNS = ("Channels", "Stim_Frequency_Hz", "Stim_Duration_ms", "UA_port", "Movement_Trigger")
RANGE_COLUMNS = ("Current_uA", "Depth_mm", "Delay")

# Output folder (relative to the session folder) and file pattern for steps that write one set of files per BR_File.
PER_BR_OUTPUTS: dict[str, tuple[str, str]] = {
    "make_aligned": ("results/checkpoints/Aligned", "aligned__*__BR_{br:03d}.npz"),
    "extract_peri": ("results/checkpoints/PeriStim", "peristim__*__BR_{br:03d}*.npz"),
    "manual_inspection": ("results/figures/kinematics_trajectories", "BR_{br:03d}_xy.jpg"),
}


@dataclass
class Condition:
    br_file: int
    values: dict[str, str]


@dataclass
class Session:
    name: str
    location: str
    conditions: list[Condition] = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)
    # Steps whose file input (e.g. manual_trial_remove.csv) changed for this session since they last ran.
    stale_file_inputs: set[str] = field(default_factory=set)
    # Steps whose raw input doesn't exist for this session, e.g. UA_BR_analysis with no .ns6 files.
    unavailable_steps: set[str] = field(default_factory=set)
    # Data problems to show on the Sessions step (missing raw files, unreadable status values, ...).
    notes: list[str] = field(default_factory=list)


def trial_remove_csv_path() -> Path:
    return paths.repo_root() / "config" / "manual_trial_remove.csv"


class DataRootError(Exception):
    pass


def animal_root(animal: str) -> Path:
    config = paths.repo_root() / "config"
    machines = (yaml.safe_load((config / "machines.yaml").read_text()) or {}).get("machines") or {}
    hostname = socket.gethostname()
    if hostname not in machines:
        raise DataRootError(f"This computer ({hostname}) has no entry in config/machines.yaml")
    relative = yaml.safe_load((config / "params.yaml").read_text())["paths"]["data_root"]
    return Path(paths.params_loading()._resolve_data_root(config / "machines.yaml", relative)) / animal


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean_status(raw: str | None) -> str:
    """Map a data_status_reaching.csv cell to '', 'DONE', 'FAIL', 'IN-PROGRESS' or a timestamp string.

    Anything unrecognised becomes '' (not run) so the planner never silently skips it.
    """
    value = (raw or "").strip()
    upper = value.upper()
    if upper in ("DONE", "FAIL", "IN-PROGRESS"):
        return upper
    if paths.hierarchy().parse_status_timestamp(value) is not None:
        return value
    return ""


def clean_meta(raw: str | None) -> str:
    value = (raw or "").strip()
    return "" if value == "-" else value


def _as_index(raw: str) -> int | None:
    try:
        return int(float(raw))
    except ValueError:
        return None


def load_conditions(metadata_csv: Path) -> list[Condition]:
    conditions = []
    for row in _read_csv(metadata_csv):
        values = {k.strip(): clean_meta(v) for k, v in row.items() if k}
        br = _as_index(values.get("BR_File", ""))
        if br is not None:
            conditions.append(Condition(br_file=br, values=values))
    return conditions


def _list_dir(folder: Path) -> list[tuple[str, bool]]:
    """(name, is_dir) for each entry, from one directory listing; much faster than per-file stat on a network share."""
    try:
        with os.scandir(folder) as entries:
            return [(e.name, e.is_dir()) for e in entries]
    except FileNotFoundError:
        return []


def check_raw_files(root: Path, session: Session) -> tuple[list[str], set[str]]:
    """Return (notes about missing raw files, steps that can't run for this session)."""
    loc = root / session.location
    blackrock = _list_dir(loc / "Blackrock")
    ns5 = [name[:-4] for name, is_dir in blackrock if not is_dir and name.endswith(".ns5")]
    ns6 = [name[:-4] for name, is_dir in blackrock if not is_dir and name.endswith(".ns6")]
    intan_count = sum(1 for _, is_dir in _list_dir(loc / "Intan") if is_dir)
    # Raw .avi files sit in Video/ (older sessions) or Raw Video/; DLC CSVs in Video/DLC. Any of them proves the video.
    video_names = [name for folder in (loc / "Video", loc / "Raw Video", loc / "Video" / "DLC")
                   for name, is_dir in _list_dir(folder) if not is_dir]
    vog_names = [name for name, is_dir in _list_dir(loc / "VOG") if not is_dir]

    notes: list[str] = []
    ua_missing: list[str] = []
    vog_listed = 0
    vog_missing: list[str] = []
    for c in session.conditions:
        br = f"{c.br_file:03d}"
        if not any(stem.endswith(br) for stem in ns5):
            notes.append(f"BR_File {c.br_file}: no Blackrock .ns5")
        if not any(stem.endswith(br) for stem in ns6):
            ua_missing.append(f"BR_File {c.br_file}: no Blackrock .ns6 (UA data)")

        intan = _as_index(c.values.get("Intan_File", ""))
        if intan is not None and not 1 <= intan <= intan_count:
            notes.append(f"BR_File {c.br_file}: Intan_File {intan} but only {intan_count} Intan folders")

        video = _as_index(c.values.get("Video_File", ""))
        if video is not None and not any(f"_{video:03d}_" in n for n in video_names):
            notes.append(f"BR_File {c.br_file}: Video_File {video} not found in Video/, Raw Video/ or Video/DLC/")

        vog = _as_index(c.values.get("VOG_File", ""))
        if vog is not None:
            vog_listed += 1
            if not any(f"_{vog:03d}_" in n for n in vog_names):
                vog_missing.append(f"BR_File {c.br_file}: VOG_File {vog} not found in VOG/")

    # A whole session without the data means the step can't run (n/a); a few gaps are per-condition problems.
    unavailable: set[str] = set()
    if session.conditions and len(ua_missing) == len(session.conditions):
        unavailable.add("UA_BR_analysis")
        notes.append("No Blackrock .ns6 (UA data) for any BR_File: UA_BR_analysis is n/a")
    else:
        notes += ua_missing
    if vog_listed and len(vog_missing) == vog_listed:
        unavailable.add("VOG")
        notes.append("VOG_File is listed but there are no VOG files: VOG is n/a")
    else:
        notes += vog_missing
    return notes, unavailable


def _normalise_trials(raw: str) -> str:
    try:
        return ",".join(str(t) for t in sorted({int(x) for x in raw.split(",") if x.strip()}))
    except ValueError:
        return raw.strip()


def trial_remove_fingerprint(csv_path: Path, session_name: str) -> str:
    """Hash of this session's rows in manual_trial_remove.csv (br_idx + trials_to_drop only)."""
    lines = sorted(
        f"{row['br_idx'].strip()}:{_normalise_trials(row['trials_to_drop'] or '')}"
        for row in _read_csv(csv_path)
        if (name := (row.get("intan_filename") or "").strip()) == session_name or name.startswith(session_name + "_")
    )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def fingerprint_path(root: Path, session: Session) -> Path:
    return root / session.location / "results" / "checkpoints" / "PeriStim" / FINGERPRINT_NAME


def check_trial_remove(root: Path, session: Session, csv_path: Path | None = None) -> tuple[set[str], list[str]]:
    """Return (stale steps, notes). extract_peri is stale if its saved fingerprint differs from the CSV now."""
    csv_path = csv_path or trial_remove_csv_path()
    if not session.status.get("extract_peri") or not csv_path.exists():
        return set(), []
    saved = fingerprint_path(root, session)
    if not saved.exists():
        return set(), ["extract_peri: no saved manual_trial_remove fingerprint, so trial-removal edits can't be checked"]
    if saved.read_text().strip() != trial_remove_fingerprint(csv_path, session.name):
        return {"extract_peri"}, []
    return set(), []


def load_sessions(root: Path, trial_remove_csv: Path | None = None) -> dict[str, Session]:
    """Every session in data_status_reaching.csv that has a Metadata/<session>_metadata.csv."""
    status_csv = root / STATUS_CSV_NAME
    if not status_csv.exists():
        raise FileNotFoundError(f"{STATUS_CSV_NAME} not found: {status_csv}")

    steps = list(paths.hierarchy().COLUMN_DEPENDENCIES)

    def load_one(row: dict[str, str]) -> Session | None:
        name = (row.get("Session") or "").strip()
        location = (row.get("Location") or "").strip()
        metadata_csv = root / location / "Metadata" / f"{name}_metadata.csv"
        if not name or not metadata_csv.exists():
            return None

        session = Session(name=name, location=location, conditions=load_conditions(metadata_csv))
        for step in steps:
            raw = (row.get(step) or "").strip()
            session.status[step] = clean_status(raw)
            if raw and not session.status[step] and raw.upper() != "NOT STARTED":
                session.notes.append(f"{step}: unrecognised status '{raw}', treated as not run")

        raw_notes, session.unavailable_steps = check_raw_files(root, session)
        session.stale_file_inputs, trial_notes = check_trial_remove(root, session, trial_remove_csv)
        session.notes += raw_notes + trial_notes
        return session

    # Each session is a handful of independent network reads, so overlap them.
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(load_one, _read_csv(status_csv)))
    sessions = {s.name: s for s in loaded if s is not None}
    return sessions


def _sort_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def filter_options(sessions: dict[str, Session], columns: tuple[str, ...] = CHIP_COLUMNS) -> dict[str, list[str]]:
    """Distinct non-empty values per column across all conditions of the given sessions (chips in §2.6)."""
    options: dict[str, set[str]] = {col: set() for col in columns}
    for session in sessions.values():
        for c in session.conditions:
            for col in columns:
                if value := c.values.get(col, ""):
                    options[col].add(value)
    return {col: sorted(values, key=_sort_key) for col, values in options.items()}


def filter_conditions(
    sessions: dict[str, Session],
    chips: dict[str, set[str]],
    ranges: dict[str, tuple[float | None, float | None]],
) -> dict[str, list[int]]:
    """Apply the Conditions-step filters (§2.6) and return session -> selected BR_File indices.

    chips:  column -> values the user ticked, e.g. {"UA_port": {"A"}, "Channels": {"32", "64"}}.
    ranges: column -> (min, max); None means that end is open, e.g. {"Current_uA": (5.0, None)}.
    """
    result: dict[str, list[int]] = {}

    for name, session in sessions.items():
        selected: list[int] = []
        for c in session.conditions:
            passes = True

            for column, allowed in chips.items():
                value = c.values.get(column, "")
                if allowed and value not in allowed:
                    passes = False
                    break

            for column, (low, high) in ranges.items():
                value = c.values.get(column, "")
                if not value:
                    passes = False
                    break
                try:
                    numeric_value = float(value)
                except ValueError:
                    passes = False
                    break

                if low is not None and numeric_value < low:
                    passes = False
                    break
                if high is not None and numeric_value > high:
                    passes = False
                    break
            if passes:
                selected.append(c.br_file)
        result[name] = selected
    return result



def br_outputs(root: Path, session: Session, step: str, br_file: int) -> list[Path]:
    folder, pattern = PER_BR_OUTPUTS[step]
    return sorted((root / session.location / folder).rglob(pattern.format(br=br_file)))
