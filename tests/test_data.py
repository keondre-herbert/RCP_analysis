import csv
from pathlib import Path

import pytest

from veles.data import (
    Condition,
    Session,
    br_outputs,
    check_raw_files,
    check_trial_remove,
    clean_status,
    filter_conditions,
    filter_options,
    fingerprint_path,
    load_sessions,
    trial_remove_fingerprint,
)
from veles.planner import is_applicable

LOC = "20260116_NRR_RW012"
NAME = "NRR_RW012"


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


@pytest.fixture
def trial_csv(tmp_path) -> Path:
    return write_csv(
        tmp_path / "manual_trial_remove.csv",
        ["intan_filename", "br_idx", "trials_to_drop", "reason"],
        [
            ["NRR_RW012_260116", "3", "7, 14", "bad tracking"],
            ["NRR_RW011_251203", "3", "1", "other session"],
        ],
    )


@pytest.fixture
def root(tmp_path) -> Path:
    """A tiny copy of the real Nike layout, with one of each kind of problem."""
    root = tmp_path / "Nike"
    write_csv(
        root / "data_status_reaching.csv",
        ["Process Session?", "Location", "Session", "OCR", "DLC", "NPRW_Intan_analysis", "compute_shifts", "extract_peri"],
        [
            ["No", LOC, NAME, "done", "Not started", "09/01/2026 10:00:00", "maybe", "2026-09-02 10:00:00"],
            ["No", "20260117_NRR_RW013", "NRR_RW013", "done", "", "", "", ""],  # no metadata CSV
        ],
    )
    write_csv(
        root / LOC / "Metadata" / f"{NAME}_metadata.csv",
        ["BR_File", "Intan_File", "Video_File", "VOG_File", "Channels", "Current_uA", "UA_port", "Notes"],
        [
            ["2", "1", "3", "-", "-", "-", "A", "Baseline"],
            ["3", "2", "4", "-", "32", "5", "A", "Rest"],
            ["4", "3", "5", "-", "64", "10", "B", "Rest"],
            ["x", "", "", "", "", "", "", "not a BR row"],
        ],
    )
    for name in ("NRR_RW012_002.ns5", "NRR_RW012_002.ns6", "NRR_RW012_003.ns5", "NRR_RW012_003.ns6"):
        touch(root / LOC / "Blackrock" / name)
    for folder in ("NRR_RW012_260116_131117", "NRR_RW012_260116_140816", "NRR_RW012_260116_141228"):
        (root / LOC / "Intan" / folder).mkdir(parents=True)
    touch(root / LOC / "Video" / "DLC" / "NRR_RW012_003_Cam-0DLC.csv")
    touch(root / LOC / "Video" / "DLC" / "NRR_RW012_004_Cam-0DLC.csv")
    return root


# --- clean_status ---

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", ""),
        (None, ""),
        ("Not started", ""),
        ("done", "DONE"),
        (" FAIL ", "FAIL"),
        ("in-progress", "IN-PROGRESS"),
        ("09/17/2026 13:26:49", "09/17/2026 13:26:49"),
        ("8/31/2026 10:17", "8/31/2026 10:17"),
        ("maybe", ""),
    ],
)
def test_clean_status(raw, expected):
    assert clean_status(raw) == expected


# --- load_sessions ---

def test_only_sessions_with_a_metadata_csv_are_loaded(root, trial_csv):
    assert list(load_sessions(root, trial_csv)) == [NAME]


def test_missing_status_csv_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_sessions(tmp_path)


def test_status_values_are_cleaned(root, trial_csv):
    s = load_sessions(root, trial_csv)[NAME]
    assert s.status["OCR"] == "DONE"
    assert s.status["DLC"] == ""
    assert s.status["compute_shifts"] == ""
    assert s.status["make_aligned"] == ""  # column not in the file
    assert "compute_shifts: unrecognised status 'maybe', treated as not run" in s.notes
    assert not any(n.startswith("DLC") for n in s.notes)  # "Not started" is expected, not a problem


def test_conditions_skip_bad_rows_and_blank_out_dashes(root, trial_csv):
    s = load_sessions(root, trial_csv)[NAME]
    assert [c.br_file for c in s.conditions] == [2, 3, 4]
    assert s.conditions[0].values["Channels"] == ""
    assert s.conditions[1].values["Channels"] == "32"


# --- raw files ---

def test_missing_raw_files_are_noted(root, trial_csv):
    notes = load_sessions(root, trial_csv)[NAME].notes
    assert "BR_File 4: no Blackrock .ns5" in notes
    assert "BR_File 4: no Blackrock .ns6 (UA data)" in notes
    assert "BR_File 4: Video_File 5 not found in Video/" in notes
    assert not any(n.startswith(("BR_File 2", "BR_File 3")) for n in notes)


def test_intan_index_out_of_range_is_noted(root):
    s = Session(NAME, LOC, [Condition(2, {"Intan_File": "4"})])
    notes, _ = check_raw_files(root, s)
    assert "BR_File 2: Intan_File 4 but only 3 Intan folders" in notes


def test_no_ns6_for_any_br_makes_ua_analysis_na(tmp_path):
    touch(tmp_path / LOC / "Blackrock" / "NRR_RW002_001.ns5")
    s = Session("NRR_RW002", LOC, [Condition(1, {})])
    notes, unavailable = check_raw_files(tmp_path, s)
    s.unavailable_steps = unavailable
    assert unavailable == {"UA_BR_analysis"}
    assert not is_applicable("UA_BR_analysis", s)
    assert is_applicable("make_aligned", s)
    assert notes == ["No Blackrock .ns6 (UA data) for any BR_File: UA_BR_analysis is n/a"]


def test_vog_listed_but_no_vog_files_makes_vog_na(tmp_path):
    s = Session(NAME, LOC, [Condition(2, {"VOG_File": "2"}), Condition(3, {"VOG_File": "3"})])
    notes, unavailable = check_raw_files(tmp_path, s)
    assert "VOG" in unavailable
    assert "VOG_File is listed but there are no VOG files: VOG is n/a" in notes
    assert not any("VOG_File 2" in n for n in notes)


def test_one_missing_vog_file_is_a_per_br_note(tmp_path):
    touch(tmp_path / LOC / "VOG" / "NRR_RW012_002_2026_0116_131117.csv")
    s = Session(NAME, LOC, [Condition(2, {"VOG_File": "2"}), Condition(3, {"VOG_File": "3"})])
    notes, unavailable = check_raw_files(tmp_path, s)
    assert "VOG" not in unavailable
    assert "BR_File 3: VOG_File 3 not found in VOG/" in notes


# --- manual_trial_remove fingerprint ---

def test_fingerprint_only_looks_at_this_sessions_trials(tmp_path, trial_csv):
    before = trial_remove_fingerprint(trial_csv, NAME)
    edited = write_csv(
        tmp_path / "edited.csv",
        ["intan_filename", "br_idx", "trials_to_drop", "reason"],
        [
            ["NRR_RW012_260116", "3", "14,7", "reason reworded"],  # same trials, new order/spacing/reason
            ["NRR_RW011_251203", "3", "1, 2", "other session changed"],
        ],
    )
    assert trial_remove_fingerprint(edited, NAME) == before

    dropped_more = write_csv(
        tmp_path / "more.csv",
        ["intan_filename", "br_idx", "trials_to_drop", "reason"],
        [["NRR_RW012_260116", "3", "7, 14, 20", "bad tracking"]],
    )
    assert trial_remove_fingerprint(dropped_more, NAME) != before


def test_extract_peri_without_saved_fingerprint_gets_a_note(root, trial_csv):
    s = load_sessions(root, trial_csv)[NAME]
    assert s.stale_file_inputs == set()
    assert any("fingerprint" in n for n in s.notes)


def test_changed_fingerprint_makes_extract_peri_stale(root, trial_csv):
    s = load_sessions(root, trial_csv)[NAME]
    saved = fingerprint_path(root, s)
    saved.parent.mkdir(parents=True, exist_ok=True)

    saved.write_text(trial_remove_fingerprint(trial_csv, NAME))
    assert check_trial_remove(root, s, trial_csv) == (set(), [])

    saved.write_text("an old fingerprint")
    assert check_trial_remove(root, s, trial_csv) == ({"extract_peri"}, [])


def test_no_fingerprint_check_before_extract_peri_has_run(root, trial_csv):
    s = Session(NAME, LOC, status={"extract_peri": ""})
    assert check_trial_remove(root, s, trial_csv) == (set(), [])


# --- outputs ---

def test_br_outputs_finds_files_in_category_subfolders(root):
    peri = root / LOC / "results" / "checkpoints" / "PeriStim"
    a = touch(peri / "stim_reaches" / "peristim__NRR_RW012_260116_131117__BR_003.npz")
    b = touch(peri / "stim_reaches" / "target_A" / "peristim__NRR_RW012_260116_131117__BR_003_target_A.npz")
    touch(peri / "stim_reaches" / "peristim__NRR_RW012_260116_131117__BR_030.npz")
    s = Session(NAME, LOC)
    assert br_outputs(root, s, "extract_peri", 3) == sorted([a, b])
    assert br_outputs(root, s, "make_aligned", 3) == []


# --- filter_options ---

def test_filter_options_are_distinct_sorted_and_skip_blanks(root, trial_csv):
    options = filter_options(load_sessions(root, trial_csv))
    assert options["Channels"] == ["32", "64"]
    assert options["UA_port"] == ["A", "B"]
    assert options["Stim_Frequency_Hz"] == []


# --- filter_conditions (unambiguous cases only) ---

@pytest.fixture
def two_sessions() -> dict[str, Session]:
    return {
        "S1": Session("S1", "L1", [
            Condition(1, {"UA_port": "A", "Current_uA": "5"}),
            Condition(2, {"UA_port": "B", "Current_uA": "10"}),
        ]),
        "S2": Session("S2", "L2", [Condition(7, {"UA_port": "A", "Current_uA": "20"})]),
    }


def test_no_filters_selects_everything(two_sessions):
    assert filter_conditions(two_sessions, {}, {}) == {"S1": [1, 2], "S2": [7]}


def test_chip_filter(two_sessions):
    assert filter_conditions(two_sessions, {"UA_port": {"A"}}, {}) == {"S1": [1], "S2": [7]}


def test_range_is_inclusive_and_sessions_with_no_match_stay_in_the_result(two_sessions):
    assert filter_conditions(two_sessions, {}, {"Current_uA": (5.0, 10.0)}) == {"S1": [1, 2], "S2": []}


def test_open_ended_range(two_sessions):
    assert filter_conditions(two_sessions, {}, {"Current_uA": (None, 9.0)}) == {"S1": [1], "S2": []}


def test_chips_and_ranges_must_all_match(two_sessions):
    assert filter_conditions(two_sessions, {"UA_port": {"A"}}, {"Current_uA": (10.0, None)}) == {"S1": [], "S2": [7]}
