"""Phenology & crop-history inference from NDVI time series. (TASK-E01, E02, E03)

Pipeline:
    raw NDVI (gee.ndvi_timeseries or regional HLS phenology)
      -> smooth()            : resample to 5-day, interpolate gaps, Savitzky-Golay
      -> detect_seasons()    : peaks with prominence >= 0.15 NDVI, start/end at 20% amplitude
      -> classify_season()   : rule-based Indian agro-climatic crop group inference
      -> list[InferredSeason]  (terraloop_schemas)

Indian agro-climatic rules of thumb for E02:
    * Kharif peak Aug-Oct, start Jun-Jul           -> rice (high peak >= 0.65) / cotton / maize / sorghum
    * Rabi peak Jan-Mar, start Nov-Dec             -> wheat / chickpea / mustard / rice-fallow urad
    * Zaid peak May, start Apr                     -> summer moong / urad
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

    resampled = s.resample("5D").mean()
    interpolated = resampled.interpolate(method="time").bfill().ffill()

    vals = np.clip(interpolated.to_numpy(dtype=float), -0.2, 1.0)
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

    peaks: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] >= 0.30:
            peaks.append(i)

    seasons: list[dict[str, Any]] = []

    for p_idx in peaks:
        p_val = float(y[p_idx])

        left_window = max(0, p_idx - 30)
        left_base = float(np.min(y[left_window:p_idx])) if p_idx > left_window else 0.2

        right_window = min(len(y), p_idx + 31)
        right_base = float(np.min(y[p_idx:right_window])) if right_window > p_idx else 0.2

        base_val = max(0.1, min(left_base, right_base))
        prominence = p_val - base_val

        if prominence < prominence_threshold:
            continue

        amplitude = prominence
        threshold_20 = base_val + 0.20 * amplitude

        start_idx = p_idx
        for j in range(p_idx, left_window - 1, -1):
            if y[j] <= threshold_20:
                start_idx = j
                break

        end_idx = p_idx
        for j in range(p_idx, right_window):
            if y[j] <= threshold_20:
                end_idx = j
                break

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
    """TASK-E02: Rule-based classification of Indian crop group and season index.

    Rules across Indian agro-climatic zones:
      - Kharif (season_index 0): Peak in Jul-Nov (months 7-11).
        * High NDVI peak (>= 0.65): 'rice' ('rice_puddled')
        * SW Punjab Cotton Belt / Vidarbha Deccan: 'cotton'
        * Bundelkhand Semi-Arid: 'sorghum'
        * Default moderate Kharif peak: 'maize'
      - Rabi (season_index 1): Peak in Dec-Apr (months 12, 1-4).
        * Cauvery Delta (lat < 15.0): 'urad' (rice-fallow blackgram)
        * Vidarbha Rainfed Vertisol: 'chickpea'
        * Early Jan peak with moderate NDVI (< 0.60): 'mustard'
        * Default irrigated Rabi cereal: 'wheat'
      - Zaid (season_index 2): Peak in May-Jun (months 5-6).
        * Summer pulse: 'moong'
    """
    p_date: date = season["peak"]
    s_date: date = season["start"]
    e_date: date = season["end"]
    p_val: float = season.get("peak_value", 0.6)

    p_month = p_date.month

    is_sw_punjab = (28.5 <= lat <= 31.2) and (73.5 <= lon < 75.2)
    is_vidarbha = (18.0 <= lat < 23.0) and (75.0 <= lon <= 80.5)
    is_bundelkhand = (23.5 <= lat < 27.0) and (77.5 <= lon <= 81.5)
    is_cauvery_delta = lat < 15.0

    if p_month in (7, 8, 9, 10, 11):
        season_index = 0
        if p_val >= 0.65 or is_cauvery_delta:
            crop_group = "rice"
            crop_id = "rice_puddled"
        elif is_sw_punjab or is_vidarbha:
            crop_group = "cotton"
            crop_id = "cotton"
        elif is_bundelkhand:
            crop_group = "sorghum"
            crop_id = "sorghum"
        else:
            crop_group = "maize"
            crop_id = "maize"
    elif p_month in (12, 1, 2, 3, 4):
        season_index = 1
        if is_cauvery_delta:
            crop_group = "rice"
            crop_id = "rice_puddled"
        elif is_vidarbha:
            crop_group = "chickpea"
            crop_id = "chickpea"
        elif p_month == 1 and p_val < 0.60 and not is_bundelkhand:
            crop_group = "mustard"
            crop_id = "mustard"
        else:
            crop_group = "wheat"
            crop_id = "wheat"
    else:
        season_index = 2
        crop_group = "moong"
        crop_id = "moong"

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
    """Full pipeline: irregular NDVI -> smoothed -> detected seasons -> classified crop history.

    Orders seasons within each year by (year, season_index) so Kharif (0) precedes Rabi (1) and Zaid (2).
    """
    if ndvi.empty:
        return []
    smoothed = smooth(ndvi)
    seasons = detect_seasons(smoothed)
    inferred = [classify_season(s, lat, lon) for s in seasons]
    inferred.sort(key=lambda s: (s.year, s.season_index))
    return inferred
