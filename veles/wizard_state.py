"""Everything the New run wizard collects, shared by its five pages. No Qt."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from veles import paths
from veles.data import Session, filter_conditions
from veles.planner import Plan, Policy, RunRequest, build_plan, is_applicable, stale_reasons

# The status strip on the Sessions step: (status column, short label).
STRIP: tuple[tuple[str, str], ...] = (
    ("OCR", "OCR"),
    ("DLC", "DLC"),
    ("VOG", "VOG"),
    ("NPRW_Intan_analysis", "NPRW"),
    ("compute_shifts", "SHIFT"),
    ("UA_BR_analysis", "UA"),
    ("make_aligned", "ALIGN"),
    ("extract_peri", "PERI"),
)

StripState = Literal["ok", "stale", "failed", "missing", "na"]
STRIP_LABELS: dict[str, str] = {"ok": "Up to date", "stale": "Stale", "failed": "Failed", "missing": "Not run", "na": "n/a"}


def strip_state(session: Session, step: str) -> StripState:
    """One cell of the Sessions status strip: how `step` stands for `session` right now.

    Building blocks: is_applicable(step, session), stale_reasons(step, session) (a list; empty = not stale),
    and session.status[step], which data.clean_status already reduced to '', 'DONE', 'FAIL', 'IN-PROGRESS'
    or a timestamp.
    """
    # TODO(human)
    return "missing"


def last_processed(session: Session):
    """Newest timestamp in the session's status row, or None."""
    parse = paths.hierarchy().parse_status_timestamp
    times = [t for v in session.status.values() if (t := parse(v)) is not None]
    return max(times, default=None)


def raw_file_problems(session: Session) -> list[str]:
    """Per-BR missing raw files. Whole-session gaps ('... is n/a') show up as n/a in the strip instead."""
    return [n for n in session.notes if n.startswith("BR_File")]


@dataclass
class WizardState:
    animal: str = ""
    root: Path | None = None
    sessions: dict[str, Session] = field(default_factory=dict)  # every loaded session, in CSV order
    selected: list[str] = field(default_factory=list)            # kept in the same order as `sessions`
    filter_mode: Literal["all", "filter"] = "all"
    chips: dict[str, set[str]] = field(default_factory=dict)
    ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    overrides: dict[str, dict[int, bool]] = field(default_factory=dict)  # session -> BR_File -> forced on/off
    targets: list[str] = field(default_factory=list)                     # status columns the user ticked
    ua_variant: Literal["ssmf", "mf"] = "ssmf"
    policy: Policy = "needed"
    on_failure: Literal["skip_session", "stop_run"] = "skip_session"

    def use_animal(self, animal: str, root: Path, sessions: dict[str, Session]) -> None:
        """A (re)scanned animal invalidates everything chosen after it."""
        fresh = WizardState(animal=animal, root=root, sessions=sessions)
        self.__dict__.update(fresh.__dict__)

    def set_selected(self, names) -> None:
        wanted = set(names)
        self.selected = [n for n in self.sessions if n in wanted]

    def selected_sessions(self) -> dict[str, Session]:
        return {n: self.sessions[n] for n in self.selected}

    def filtered(self) -> dict[str, list[int]]:
        """BR_Files per selected session from the filters alone, before per-session clicks."""
        chosen = self.selected_sessions()
        if self.filter_mode == "all":
            return {n: [c.br_file for c in s.conditions] for n, s in chosen.items()}
        return filter_conditions(chosen, self.chips, self.ranges)

    def conditions(self) -> dict[str, list[int]]:
        """Final session -> BR_File list: the filters, then each session's clicked chips on top."""
        result = {}
        for name, brs in self.filtered().items():
            forced = self.overrides.get(name, {})
            keep = {br for br in brs if forced.get(br, True)} | {br for br, on in forced.items() if on}
            result[name] = sorted(keep)
        return result

    def request(self) -> RunRequest:
        return RunRequest(
            animal=self.animal,
            conditions=self.conditions(),
            targets=list(self.targets),
            ua_variant=self.ua_variant,
            policy=self.policy,
            on_failure=self.on_failure,
        )

    def plan(self) -> Plan | None:
        if not self.targets or not self.selected:
            return None
        return build_plan(self.request(), self.selected_sessions())

    def subtitle(self, upto_step: int) -> str:
        """Header text after "New run", growing with each step: 'Nike · 8 sessions · 37 conditions'."""
        parts = [self.animal] if self.animal else []
        if upto_step >= 2 and self.selected:
            parts.append(f"{len(self.selected)} sessions")
        if upto_step >= 3 and self.selected:
            parts.append(f"{sum(map(len, self.conditions().values()))} conditions")
        return " · ".join(parts)
