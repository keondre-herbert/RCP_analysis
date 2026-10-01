"""The scripts the wizard offers (from VELES_gui.SCRIPT_CATALOG), and how they map to status columns. No Qt."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from veles import paths

GROUPS = ("Preprocessing", "Analysis", "Nikita scripts")
UA_COLUMN = "UA_BR_analysis"
DEFAULT_UA_VARIANT = "ssmf"


@dataclass(frozen=True)
class Script:
    path: str                     # relative to the repo, forward slashes
    group: str
    manual: bool = False          # a human reviews its output (SPEC §5.4)
    all_conditions: bool = False  # ignores RCP_PROCESS_ONLY, so it always processes every BR_File of the session
    variant: str = ""             # "mf" / "ssmf" for the two UA_BR_analysis scripts

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).name

    @property
    def column(self) -> str:
        return paths.hierarchy().SCRIPT_STATUS_COLUMNS[self.name]


CATALOG: tuple[Script, ...] = (
    Script("preprocessing_scripts/OCR_frame_correction.py", "Preprocessing", all_conditions=True),
    Script("preprocessing_scripts/align_dlc_two_cams_to_br.py", "Preprocessing", all_conditions=True),
    Script("preprocessing_scripts/align_VOG_to_br.py", "Preprocessing", all_conditions=True),
    Script("preprocessing_scripts/NPRW_Intan_analysis_mf.py", "Preprocessing"),
    Script("preprocessing_scripts/compute_br_to_intan_shifts.py", "Preprocessing"),
    Script("preprocessing_scripts/UA_BR_analysis_ssmf.py", "Preprocessing", variant="ssmf"),
    Script("preprocessing_scripts/UA_BR_analysis_mf.py", "Preprocessing", variant="mf"),
    Script("preprocessing_scripts/make_aligned_npz_and_mat.py", "Preprocessing"),
    Script("preprocessing_scripts/extract_peri_stim.py", "Preprocessing"),
    Script("preprocessing_scripts/inspect_kinematics_trajectories.py", "Preprocessing", manual=True, all_conditions=True),
    Script("preprocessing_scripts/analyze_lfp_bands.py", "Preprocessing", all_conditions=True),
    Script("analysis_scripts/plot_plateau_analysis.py", "Analysis", all_conditions=True),
    Script("analysis_scripts/RSA_calculation.py", "Analysis", all_conditions=True),
    Script("analysis_scripts/plot_firing_rates.py", "Analysis"),
    Script("analysis_scripts/plot_peri_stim_raster.py", "Analysis"),
    Script("analysis_scripts/plot_stim_group_responses.py", "Analysis"),
    Script("analysis_scripts/plot_stim_response_overlays.py", "Analysis"),
    Script("analysis_scripts/plot_peak_csv_summaries.py", "Analysis", all_conditions=True),
    Script("analysis_scripts/plot_bin_counts_per_target.py", "Analysis"),
    Script("scripts/nikita_scripts/lfp_processing/plot_lfp_cleaner.py", "Nikita scripts", all_conditions=True),
    Script("scripts/nikita_scripts/plotting_scripts/combine_UA_gifs.py", "Nikita scripts", all_conditions=True),
)


def entries(ua_variant: str = DEFAULT_UA_VARIANT) -> list[Script]:
    """Catalog as shown in the Scripts step: one UA_BR_analysis entry, the chosen variant."""
    return [s for s in CATALOG if not s.variant or s.variant == ua_variant]


def script_for(column: str, ua_variant: str = DEFAULT_UA_VARIANT) -> Script:
    for script in entries(ua_variant):
        if script.column == column:
            return script
    raise KeyError(f"No catalog script writes status column '{column}'")
