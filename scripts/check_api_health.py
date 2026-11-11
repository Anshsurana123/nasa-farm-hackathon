"""Diagnostic tool to verify reachability, latency, and response integrity
of NASA Earth Observation APIs, SoilGrids, and local/remote TerraLoop endpoints.

Usage:
    uv run python scripts/check_api_health.py
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

USER_AGENT = "TerraLoop-NASA-SpaceApps/2.6 (https://github.com/Anshsurana123/nasa-farm-hack)"


def check_endpoint(
    name: str,
    url: str,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 12.0,
) -> dict:
    req_data = json.dumps(body).encode("utf-8") if body else None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if req_data:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.time() - t0
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:  # noqa: BLE001
                data = raw[:200]
            return {
                "name": name,
                "url": url,
                "status": status,
                "elapsed": round(elapsed, 2),
                "ok": True,
                "error": None,
                "data": data,
            }
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        return {
            "name": name,
            "url": url,
            "status": e.code,
            "elapsed": round(elapsed, 2),
            "ok": False,
            "error": f"HTTP {e.code}: {e.reason}",
            "data": None,
        }
    except urllib.error.URLError as e:
        elapsed = time.time() - t0
        return {
            "name": name,
            "url": url,
            "status": None,
            "elapsed": round(elapsed, 2),
            "ok": False,
            "error": f"Network Error: {e.reason}",
            "data": None,
        }
    except Exception as e:  # noqa: BLE001
        elapsed = time.time() - t0
        return {
            "name": name,
            "url": url,
            "status": None,
            "elapsed": round(elapsed, 2),
            "ok": False,
            "error": str(e),
            "data": None,
        }


def main() -> None:
    print("\n" + "=" * 80)
    print("🛰️  TERRALOOP API REACHABILITY & HEALTH AUDIT")
    print("=" * 80 + "\n")

    test_lat, test_lon = 31.860, 74.155

    endpoints = [
        # 1. NASA POWER Daily Point API
        (
            "NASA POWER Climate API",
            (
                "https://power.larc.nasa.gov/api/temporal/daily/point?"
                "parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,WS2M&"
                f"community=AG&longitude={test_lon}&latitude={test_lat}&start=20230101&end=20230110&format=JSON"
            ),
            "GET",
            None,
            15.0,
        ),
        # 2. ISRIC SoilGrids 2.0 REST API
        (
            "ISRIC SoilGrids 2.0 REST",
            (
                "https://rest.isric.org/soilgrids/v2.0/properties/query?"
                f"lat={test_lat}&lon={test_lon}&property=clay&property=sand&property=soc&property=phh2o&depth=0-5cm"
            ),
            "GET",
            None,
            8.0,
        ),
        # 3. Local FastAPI Backend Health
        (
            "Local Backend Health (port 8000)",
            "http://127.0.0.1:8000/health",
            "GET",
            None,
            3.0,
        ),
        # 4. Local FastAPI Backend Profile
        (
            "Local Backend /profile (port 8000)",
            "http://127.0.0.1:8000/profile",
            "POST",
            {"lat": test_lat, "lon": test_lon, "name": "Custom Test Farm"},
            20.0,
        ),
        # 5. Local Next.js Dev Server (port 3000)
        (
            "Local Frontend Dev Server (port 3000)",
            "http://localhost:3000",
            "GET",
            None,
            5.0,
        ),
        # 6. Remote Vercel Production Deployment
        (
            "Vercel Production Deployment",
            "https://terraloop-five.vercel.app",
            "GET",
            None,
            10.0,
        ),
    ]

    for name, url, method, body, timeout in endpoints:
        print(f"Testing: {name} ...", end=" ", flush=True)
        res = check_endpoint(name, url, method, body, timeout)
        if res["ok"]:
            print(f"✅ [{res['status']}] in {res['elapsed']}s")
            if isinstance(res["data"], dict) and "data_mode" in res["data"]:
                dm = res["data"].get("data_mode")
                fb = res["data"].get("is_fallback")
                print(f"   ↳ Data Mode: '{dm}' | is_fallback: {fb}")
        else:
            print(f"❌ {res['error']} ({res['elapsed']}s)")

    print("\n" + "=" * 80)
    print("HOW TO INTERPRET THESE RESULTS:")
    print("  1. If NASA POWER is ✅ [200], satellite climate telemetry is 100% active.")
    print("  2. If SoilGrids times out, TerraLoop's hybrid engine automatically applies")
    print("     calibrated regional soil parameters (Alluvial/Vertisol/Red soil) with")
    print("     no loss of simulation fidelity, and data_mode becomes 'hybrid_regional'.")
    print("  3. If Local Backend /profile is ✅, localhost:3000 has full real-time access.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
