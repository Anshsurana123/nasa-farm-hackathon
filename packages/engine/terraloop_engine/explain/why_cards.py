"""Explainability: deterministic why-cards first, LLM narration second. (TASK-X01, X02)

RULES (non-negotiable, see AGENTS.md):
  * Every number in an explanation must come from a FieldProfile / SimulationResult field.
  * Every why-card cites the DataProvenance of the numbers it uses.
  * The LLM may only rephrase/translate why-cards and call engine tools; it never invents numbers.

X01 why-card templates (examples):
  water   : "Switching {from_crop} to {to_crop} cuts irrigation by {pct}% ({mm} mm/yr) [AquaCrop].
             This matters here because groundwater is falling {grace} cm/yr [GRACE-FO]."
  heat    : "Heat-stress days rose from {a} to {b}/yr [NASA POWER]; {crop} sown {month} avoids the peak."
  soil    : "Adding {legume} supplies ~{n} kg N/ha and lifts the soil health score {d} points."
  burning : "{n} fire detections near this field in Oct-Nov [FIRMS]; retaining residue adds {c} t C/ha over 10 yrs."

X02 LLM tools to expose: get_field_profile, list_strategies, compare_strategies, run_what_if, explain_metric.
Languages: en, pa (Punjabi, Gurmukhi), hi. Translate the TEMPLATE, then fill numbers (numbers stay exact).
"""

from __future__ import annotations

from terraloop_schemas import FieldProfile, StrategyRecommendation


def why_cards(profile: FieldProfile, rec: StrategyRecommendation, baseline: StrategyRecommendation | None) -> list[str]:
    raise NotImplementedError("TASK-X01")
