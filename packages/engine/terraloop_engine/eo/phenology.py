"""Phenology & crop-history inference from NDVI time series. (TASK-E01, E02, E03)

Pipeline:
    raw NDVI (gee.ndvi_timeseries)
      -> smooth()            : resample to 5-day, interpolate gaps, Savitzky-Golay
      -> detect_seasons()    : peaks with prominence >= 0.15 NDVI, start/end at 20% amplitude
      -> classify_season()   : rule-based first (E02), ML later (E03)
      -> list[InferredSeason]  (terraloop_schemas)

Punjab rules of thumb for E02 (validate against WorldCereal + farmer confirmation):
    * Kharif peak Aug-Sep, start Jun-Jul           -> rice (if flooded signal / high peak) else maize/cotton
    * Rabi peak Feb-Mar, start Nov-Dec             -> wheat (dominant) / mustard (earlier peak, Jan)
    * Bare soil + FIRMS fire Oct-Nov               -> residue burning flag
    * Cotton: long season May-Nov, slower green-up than rice
"""

from __future__ import annotations

import pandas as pd
from terraloop_schemas import InferredSeason


def smooth(ndvi: pd.Series) -> pd.Series:
    """TASK-E01: regularise and smooth an irregular NDVI series (index = datetime)."""
    raise NotImplementedError("TASK-E01")


def detect_seasons(smoothed: pd.Series) -> list[dict]:
    """TASK-E01: return [{start, peak, end, peak_value, amplitude}] for each growing season."""
    raise NotImplementedError("TASK-E01")


def classify_season(season: dict, lat: float, lon: float) -> InferredSeason:
    """TASK-E02: rule-based crop group/crop id with confidence 0-1."""
    raise NotImplementedError("TASK-E02")


def infer_history(ndvi: pd.Series, lat: float, lon: float) -> list[InferredSeason]:
    """Full pipeline; used by the profiler (crop_history) once E01/E02 are done."""
    seasons = detect_seasons(smooth(ndvi))
    return [classify_season(s, lat, lon) for s in seasons]
