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

from terraloop_engine import region_registry
from terraloop_engine.eo import classifier as clf_mod


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

    resampled = s.resample("5D").max()
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

    # Adaptive peak & prominence threshold for sparse-canopy dryland row crops (e.g. rainfed cotton on dark Vertisols)
    p95 = float(np.percentile(y, 95))
    if p95 < 0.40:
        min_peak_ndvi = max(0.22, float(np.percentile(y, 70)))
        eff_prominence = min(prominence_threshold, max(0.07, 0.38 * float(np.max(y) - np.min(y))))
    else:
        min_peak_ndvi = 0.30
        eff_prominence = prominence_threshold

    peaks: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] >= min_peak_ndvi:
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

        if prominence < eff_prominence:
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
        * Cauvery Delta: 'urad' (rice-fallow blackgram)
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

    reg = region_registry.detect_region_config(lat, lon)
    is_sw_punjab = reg.region_id == "punjab_southwest"
    is_vidarbha = reg.region_id == "vidarbha"
    is_bundelkhand = reg.region_id == "bundelkhand"
    is_cauvery_delta = reg.region_id == "cauvery"

    if p_month in (7, 8, 9, 10, 11) or (p_month == 6 and (is_vidarbha or is_bundelkhand)):
        season_index = 0
        if is_cauvery_delta:
            crop_group = "rice"
            crop_id = "rice_puddled"
        elif is_sw_punjab or is_vidarbha:
            crop_group = "cotton"
            crop_id = "cotton"
        elif is_bundelkhand:
            crop_group = "sorghum"
            crop_id = "sorghum"
        elif p_val >= 0.65:
            crop_group = "rice"
            crop_id = "rice_puddled"
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
        elif p_month == 1 and p_val < 0.60 and not is_bundelkhand and not is_sw_punjab:
            crop_group = "mustard"
            crop_id = "mustard"
        else:
            crop_group = "wheat"
            crop_id = "wheat"
    else:
        season_index = 2
        if is_cauvery_delta:
            crop_group = "urad"
            crop_id = "urad"
        else:
            crop_group = "moong"
            crop_id = "moong"

    amplitude = float(season.get("amplitude", 0.35))
    dur_days = max(30, (e_date - s_date).days)
    clf = clf_mod.build_calibrated_phenology_classifier()
    feat = np.array(
        [[p_date.timetuple().tm_yday, s_date.timetuple().tm_yday, dur_days, p_val, p_val * dur_days * 0.65]],
        dtype=float,
    )
    ml_pred = clf.predict(feat)[0]
    ml_match = (ml_pred == crop_group) or (ml_pred == "mungbean" and crop_group in ("moong", "urad"))
    base_conf = 0.57 + 0.65 * amplitude + (0.04 if ml_match else 0.0)
    confidence = round(float(np.clip(base_conf, 0.60, 0.96)), 2)

    return InferredSeason(
        year=p_date.year,
        season_index=season_index,
        start=s_date,
        peak=p_date,
        end=e_date,
        crop_group=crop_group,
        crop_id=crop_id,
        confidence=confidence,
    )


def infer_history(ndvi: pd.Series, lat: float, lon: float) -> list[InferredSeason]:
    """Full pipeline: irregular NDVI -> smoothed -> detected seasons -> classified crop history.

    Orders seasons within each year by (year, season_index) so Kharif (0) precedes Rabi (1) and Zaid (2),
    keeping the highest-confidence peak per (year, season_index) slot.
    """
    if ndvi.empty:
        return []
    smoothed = smooth(ndvi)
    seasons = detect_seasons(smoothed)
    by_slot: dict[tuple[int, int], InferredSeason] = {}
    for s in seasons:
        inf = classify_season(s, lat, lon)
        key = (inf.year, inf.season_index)
        if key not in by_slot or inf.confidence > by_slot[key].confidence:
            by_slot[key] = inf
    inferred = list(by_slot.values())
    inferred.sort(key=lambda s: (s.year, s.season_index))
    return inferred
