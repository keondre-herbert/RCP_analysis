from pathlib import Path

import pytest

from veles import catalog, paths
from veles.data import Condition, Session
from veles.planner import CellState
from veles.wizard_state import WizardState, last_processed, strip_state

T0, T1, T2 = "09/01/2026 10:00:00", "09/01/2026 11:00:00", "09/01/2026 12:00:00"


def session(name: str, brs=(1, 2, 3), status=None, **kw) -> Session:
    return Session(name, f"loc_{name}", [Condition(b, {}) for b in brs], status=status or {}, **kw)


@pytest.fixture
def state() -> WizardState:
    s = WizardState()
    s.use_animal("Nike", Path("/data/Nike"), {n: session(n) for n in ("S1", "S2", "S3")})
    return s


# --- catalog ---

def test_every_catalog_script_has_a_status_column():
    columns = paths.hierarchy().SCRIPT_STATUS_COLUMNS
    assert all(s.name in columns for s in catalog.CATALOG)


def test_one_ua_entry_per_variant():
    for variant in ("ssmf", "mf"):
        ua = [s for s in catalog.entries(variant) if s.column == catalog.UA_COLUMN]
        assert [s.variant for s in ua] == [variant]


def test_script_for_column():
    assert catalog.script_for("extract_peri").name == "extract_peri_stim.py"
    assert catalog.script_for("UA_BR_analysis", "mf").name == "UA_BR_analysis_mf.py"
    with pytest.raises(KeyError):
        catalog.script_for("not_a_column")


# --- selection and conditions ---

def test_selection_keeps_session_order(state):
    state.set_selected({"S3", "S1"})
    assert state.selected == ["S1", "S3"]


def test_all_mode_takes_every_br(state):
    state.set_selected({"S1", "S2"})
    assert state.conditions() == {"S1": [1, 2, 3], "S2": [1, 2, 3]}


def test_overrides_switch_single_brs_on_and_off_for_one_session(state):
    state.set_selected({"S1", "S2"})
    state.overrides = {"S1": {2: False}, "S2": {}}
    assert state.conditions() == {"S1": [1, 3], "S2": [1, 2, 3]}


def test_override_can_add_back_a_filtered_out_br(state):
    state.sessions["S1"].conditions[0].values["UA_port"] = "A"
    state.sessions["S1"].conditions[1].values["UA_port"] = "B"
    state.set_selected({"S1"})
    state.filter_mode = "filter"
    state.chips = {"UA_port": {"A"}}
    assert state.conditions() == {"S1": [1]}
    state.overrides = {"S1": {2: True}}
    assert state.conditions() == {"S1": [1, 2]}


def test_choosing_an_animal_again_clears_later_choices(state):
    state.set_selected({"S1"})
    state.targets = ["extract_peri"]
    state.use_animal("Ada", Path("/data/Ada"), {})
    assert (state.animal, state.selected, state.targets) == ("Ada", [], [])


def test_plan_needs_targets_and_sessions(state):
    assert state.plan() is None
    state.set_selected({"S1"})
    state.targets = ["OCR"]
    assert state.plan().cells[("S1", "OCR")] is CellState.RUN


def test_subtitle_grows_with_the_steps(state):
    state.set_selected({"S1", "S2"})
    assert state.subtitle(0) == "Nike"
    assert state.subtitle(2) == "Nike · 2 sessions"
    assert state.subtitle(3) == "Nike · 2 sessions · 6 conditions"


def test_last_processed_is_the_newest_timestamp():
    s = session("S", status={"OCR": T0, "DLC": T2, "extract_peri": "DONE"})
    assert last_processed(s).hour == 12
    assert last_processed(session("S")) is None


# --- strip_state (the Sessions status strip) ---

@pytest.mark.parametrize(
    "status, expected",
    [
        ({"OCR": T0, "DLC": T1}, "ok"),
        ({"OCR": T0, "DLC": "DONE"}, "ok"),
        ({"OCR": T0, "DLC": ""}, "missing"),
        ({"OCR": T0}, "missing"),
        ({"OCR": T0, "DLC": "FAIL"}, "failed"),
        ({"OCR": T0, "DLC": "IN-PROGRESS"}, "failed"),
        ({"OCR": T2, "DLC": T1}, "stale"),  # OCR reran after DLC
    ],
)
def test_strip_state(status, expected):
    assert strip_state(session("S", status=status), "DLC") == expected


def test_strip_state_na_when_the_step_cannot_run():
    s = session("S", status={"OCR": T0}, unavailable_steps={"UA_BR_analysis"})
    assert strip_state(s, "UA_BR_analysis") == "na"
    assert strip_state(s, "VOG") == "na"  # no condition has a VOG_File
