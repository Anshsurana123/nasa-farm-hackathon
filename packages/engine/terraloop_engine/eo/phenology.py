"""Phenology & crop-history inference from NDVI time series. (TASK-E01, E02, E03)

Pipeline:
    raw NDVI (gee.ndvi_timeseries or synthetic HLS)
      -> smooth()            : resample to 5-day, interpolate gaps, Savitzky-Golay
      -> detect_seasons()    : peaks with prominence >= 0.15 NDVI, start/end at 20% amplitude
      -> classify_season()   : rule-based crop group inference
      -> list[InferredSeason]  (terraloop_schemas)

Punjab rules of thumb for E02 (validated against WorldCereal):
    * Kharif peak Aug-Sep, start Jun-Jul           -> rice (high peak >= 0.65) / maize / cotton
    * Rabi peak Feb-Mar, start Nov-Dec             -> wheat (dominant) / mustard (earlier peak, Jan)
    * Zaid peak May, start Apr                     -> summer moong / fodder
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from terraloop_schemas import InferredSeason


def _savgol_smooth(y: np.ndarray, window_length: int = 9) -> np.ndarray:
    """Pure NumPy Savitzky-Golay smoothing (order 2 polynomial) without scipy."""
    if len(y) < window_length:
        return y.copy()

    # Precomputed Savitzky-Golay coefficients for window=9, poly=2
    # Derived from (X^T X)^-1 X^T
    coeffs = np.array([-21, 14, 39, 54, 59, 54, 39, 14, -21], dtype=float) / 231.0

    pad_width = window_length // 2
    padded = np.pad(y, pad_width, mode="edge")
    smoothed = np.convolve(padded, coeffs, mode="valid")
    return smoothed


def smooth(ndvi: pd.Series) -> pd.Series:
    """TASK-E01: Regularise and smooth an irregular NDVI series.

    Resamples to regular 5-day intervals, linearly interpolates gaps,
    and applies Savitzky-Golay polynomial smoothing.
    """
    if ndvi.empty:
        return pd.Series(dtype=float)

    s = ndvi.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    # Resample to 5-day interval and interpolate
    resampled = s.resample("5D").mean()
    interpolated = resampled.interpolate(method="time").bfill().ffill()

    # Clip to valid NDVI bounds [-0.2, 1.0]
    vals = np.clip(interpolated.to_numpy(dtype=float), -0.2, 1.0)

    # Savitzky-Golay filter
    smoothed_vals = _savgol_smooth(vals, window_length=9)

    return pd.Series(smoothed_vals, index=interpolated.index)


def detect_seasons(smoothed: pd.Series, prominence_threshold: float = 0.15) -> list[dict[str, Any]]:
    """TASK-E01: Detect growing seasons from smoothed NDVI time series.

    Finds local peaks with prominence >= prominence_threshold,
    and determines season start/end at 20% amplitude above baseline.

    Returns:
        list of dict: [{"start": date, "peak": date, "end": date, "peak_value": float, "amplitude": float}]
    """
    if len(smoothed) < 5:
        return []

    y = smoothed.to_numpy()
    dates = smoothed.index

    # Find local peaks
    peaks: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] >= 0.30:
            peaks.append(i)

    seasons: list[dict[str, Any]] = []

    for p_idx in peaks:
        p_val = float(y[p_idx])

        # Left base: lowest value within past 30 steps (~150 days)
        left_window = max(0, p_idx - 30)
        left_base = float(np.min(y[left_window:p_idx])) if p_idx > left_window else 0.2

        # Right base: lowest value within next 30 steps (~150 days)
        right_window = min(len(y), p_idx + 31)
        right_base = float(np.min(y[p_idx:right_window])) if right_window > p_idx else 0.2

        base_val = max(0.1, min(left_base, right_base))
        prominence = p_val - base_val

        if prominence < prominence_threshold:
            continue

        amplitude = prominence
        threshold_20 = base_val + 0.20 * amplitude

        # Find start of season: scan backwards from peak
        start_idx = p_idx
        for j in range(p_idx, left_window - 1, -1):
            if y[j] <= threshold_20:
                start_idx = j
                break

        # Find end of season: scan forwards from peak
        end_idx = p_idx
        for j in range(p_idx, right_window):
            if y[j] <= threshold_20:
                end_idx = j
                break

        # Avoid redundant duplicate overlaps
        if seasons and seasons[-1]["peak"] == dates[p_idx].date():
            continue

        seasons.append(
            {
                "start": dates[start_idx].date(),
                "peak": dates[p_idx].date(),
                "end": dates[end_idx].date(),
                "peak_value": round(p_val, 3),
                "amplitude": round(amplitude, 3),
            }
        )

    return seasons


def classify_season(season: dict[str, Any], lat: float, lon: float) -> InferredSeason:
    """TASK-E02: Rule-based classification of crop group and season index.

    Rules for Indo-Gangetic Plain / Punjab:
      - Kharif (season_index 0): Peak in Aug-Sep (months 8-9) or Jul-Oct.
        If peak >= 0.65 -> 'rice'; else 'maize' or 'cotton'.
      - Rabi (season_index 1): Peak in Feb-Mar (months 2-3).
        If peak in Jan (month 1) -> 'mustard'; else 'wheat'.
      - Zaid (season_index 2): Peak in May (month 5).
        -> 'moong' (summer pulse).
    """
    p_date: date = season["peak"]
    s_date: date = season["start"]
    e_date: date = season["end"]
    p_val: float = season.get("peak_value", 0.6)

    p_month = p_date.month

    # Regional detection
    is_california = (32.0 <= lat <= 42.5) and (-125.0 <= lon <= -114.0)
    is_cornbelt = (36.0 <= lat <= 49.0) and (-105.0 <= lon <= -80.0)
    is_east_africa = (-15.0 <= lat <= 12.0) and (25.0 <= lon <= 52.0)
    is_south_asia = (20.0 <= lat <= 35.0) and (68.0 <= lon <= 90.0)

    if is_california:
        if p_month in (6, 7, 8, 9):
            season_index = 0
            crop_group = "maize" if p_val >= 0.70 else "cotton"
            crop_id = crop_group
        elif p_month in (2, 3, 4, 5):
            season_index = 1
            crop_group = "wheat"
            crop_id = "wheat"
        else:
            season_index = 2
            crop_group = "cover"
            crop_id = "cereal_rye"

    elif is_cornbelt:
        if p_month in (6, 7, 8, 9):
            season_index = 0
            crop_group = "maize" if p_val >= 0.75 else "soybean"
            crop_id = crop_group
        else:
            season_index = 1
            crop_group = "cover"
            crop_id = "cereal_rye"

    elif is_east_africa:
        if p_month in (4, 5, 6, 7):
            season_index = 0
            crop_group = "maize"
            crop_id = "maize"
        elif p_month in (10, 11, 12, 1):
            season_index = 1
            crop_group = "pigeon_pea"
            crop_id = "pigeon_pea"
        else:
            season_index = 2
            crop_group = "bean"
            crop_id = "common_bean"

    elif is_south_asia:
        # Standard Punjab / Indo-Gangetic rules
        if p_month in (7, 8, 9, 10):
            season_index = 0
            crop_group = "rice" if p_val >= 0.60 else "maize"
            crop_id = "rice_puddled" if crop_group == "rice" else "maize"
        elif p_month in (1, 2, 3, 4):
            season_index = 1
            crop_group = "mustard" if p_month == 1 else "wheat"
            crop_id = crop_group
        else:
            season_index = 2
            crop_group = "moong"
            crop_id = "moong"

    else:
        # Global temperate / subtropical fallback
        summer_months = (6, 7, 8, 9) if lat >= 0 else (12, 1, 2, 3)
        winter_months = (2, 3, 4, 5) if lat >= 0 else (8, 9, 10, 11)
        if p_month in summer_months:
            season_index = 0
            crop_group = "maize" if p_val >= 0.65 else "soybean"
            crop_id = crop_group
        elif p_month in winter_months:
            season_index = 1
            crop_group = "wheat"
            crop_id = "wheat"
        else:
            season_index = 2
            crop_group = "cover"
            crop_id = "cereal_rye"

    return InferredSeason(
        year=p_date.year,
        season_index=season_index,
        start=s_date,
        peak=p_date,
        end=e_date,
        crop_group=crop_group,
        crop_id=crop_id,
        confidence=0.85,
    )


def infer_history(ndvi: pd.Series, lat: float, lon: float) -> list[InferredSeason]:
    """Full pipeline: irregular NDVI -> smoothed -> detected seasons -> classified crop history."""
    if ndvi.empty:
        return []
    smoothed = smooth(ndvi)
    seasons = detect_seasons(smoothed)
    return [classify_season(s, lat, lon) for s in seasons]
