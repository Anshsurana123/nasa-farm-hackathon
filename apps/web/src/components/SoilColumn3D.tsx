"use client";

import { useEffect, useRef, useState } from "react";
import type { FieldProfile, StrategyRecommendation } from "@/types/api";
import { MONTHS, waterSavedPct } from "@/lib/ui";
import { useI18n } from "@/i18n";
import { ProvenanceChip } from "./ProvenanceChip";
import {
  RotateCcw,
  Play,
  Pause,
  SlidersHorizontal,
  ArrowDownUp,
  Eye,
} from "lucide-react";

interface SoilColumn3DProps {
  profile: FieldProfile;
  strategies?: StrategyRecommendation[];
}

interface Vec3 {
  x: number;
  y: number;
  z: number;
}

interface ProjectedPt {
  x: number;
  y: number;
  z: number;
  scale: number;
}

export function SoilColumn3D({ profile, strategies = [] }: SoilColumn3DProps) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Interactive 3D camera state
  const [yaw, setYaw] = useState<number>(-0.68); // radians
  const [pitch, setPitch] = useState<number>(0.48); // radians
  const [exploded, setExploded] = useState<boolean>(true);
  const [regime, setRegime] = useState<"baseline" | "recommended">("recommended");
  const [monthIdx, setMonthIdx] = useState<number>(7); // August (Kharif peak)
  const [autoPlay, setAutoPlay] = useState<boolean>(false);

  const isDraggingRef = useRef<boolean>(false);
  const lastPointerRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const explodeAnimRef = useRef<number>(1);
  const regimeAnimRef = useRef<number>(1);

  const { soil, water, hazards, climate } = profile;

  const baselineStrat = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const topStrat = strategies.find((s) => s.rank === 1) ?? strategies[1] ?? baselineStrat;

  const baseRes = baselineStrat?.results?.[0];
  const topRes = topStrat?.results?.[0];

  const savedWaterPct = topStrat ? (waterSavedPct(topStrat) ?? 24) : 24;
  const socDeltaBase = baseRes?.soc_delta_t_ha_10yr ?? -0.8;
  const socDeltaTop = topRes?.soc_delta_t_ha_10yr ?? 2.1;

  const sand = soil.sand_pct ?? 42;
  const silt = soil.silt_pct ?? 36;
  const clay = soil.clay_pct ?? 22;
  const soc = soil.soc_g_per_kg ?? 8.5;
  const slopePct = soil.slope_pct ?? 0.8;
  const gwTrend = water.groundwater_trend_cm_per_year ?? 0;
  const smapArray =
    water.root_zone_moisture_percentile && water.root_zone_moisture_percentile.length === 12
      ? water.root_zone_moisture_percentile
      : [42, 45, 38, 30, 25, 35, 62, 74, 68, 52, 44, 41];
  const currentSmap = smapArray[monthIdx] ?? 50;
  const monthlyRain = climate.monthly_precip_mm?.[monthIdx] ?? 45;

  // Auto-advance month when playing
  useEffect(() => {
    if (!autoPlay) return;
    const id = window.setInterval(() => {
      setMonthIdx((prev) => (prev + 1) % 12);
    }, 950);
    return () => window.clearInterval(id);
  }, [autoPlay]);

  // High-DPI ResizeObserver (following modern-web-guidance devicePixelContentBoxSize rule)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const dpc = (entry as unknown as { devicePixelContentBoxSize?: ReadonlyArray<{ inlineSize: number; blockSize: number }> })
        .devicePixelContentBoxSize;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = dpc && dpc[0]
        ? dpc[0].inlineSize
        : Math.max(1, Math.round(entry.contentRect.width * dpr));
      canvas.height = dpc && dpc[0]
        ? dpc[0].blockSize
        : Math.max(1, Math.round(entry.contentRect.height * dpr));
    });

    const supportsDpc =
      typeof ResizeObserverEntry !== "undefined" &&
      "devicePixelContentBoxSize" in ResizeObserverEntry.prototype;
    observer.observe(canvas, supportsDpc ? { box: "device-pixel-content-box" } : undefined);

    return () => observer.disconnect();
  }, []);

  // Main 3D Canvas Render Loop
  useEffect(() => {
    let rafId = 0;
    const startTime = performance.now();

    const project = (
      p: Vec3,
      cx: number,
      cy: number,
      scale: number,
      cosY: number,
      sinY: number,
      cosP: number,
      sinP: number
    ): ProjectedPt => {
      // Rotate around Y (azimuth)
      const x1 = p.x * cosY - p.z * sinY;
      const z1 = p.x * sinY + p.z * cosY;
      // Rotate around X (elevation pitch)
      const y2 = p.y * cosP - z1 * sinP;
      const z2 = p.y * sinP + z1 * cosP;
      // Perspective division
      const fov = 4.6;
      const persp = fov / Math.max(1.5, fov + z2 * 0.42);
      return {
        x: cx + x1 * scale * persp,
        y: cy - y2 * scale * persp,
        z: z2,
        scale: persp,
      };
    };

    const drawQuad = (
      ctx: CanvasRenderingContext2D,
      pts: [ProjectedPt, ProjectedPt, ProjectedPt, ProjectedPt],
      fill: string | CanvasGradient,
      stroke?: string,
      lineWidth = 1
    ) => {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      ctx.lineTo(pts[1].x, pts[1].y);
      ctx.lineTo(pts[2].x, pts[2].y);
      ctx.lineTo(pts[3].x, pts[3].y);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
      }
    };

    const drawSlab = (
      ctx: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      scale: number,
      cosY: number,
      sinY: number,
      cosP: number,
      sinP: number,
      yTop: number,
      yBot: number,
      slopeTilt: number,
      colors: { top: string; left: string; right: string; stroke: string },
      halfW = 1.05
    ) => {
      // 8 corners of the rectangular prism, with top tilted slightly by slopeTilt
      const topCorners: Vec3[] = [
        { x: -halfW, y: yTop + slopeTilt, z: -halfW },
        { x: halfW, y: yTop - slopeTilt, z: -halfW },
        { x: halfW, y: yTop - slopeTilt, z: halfW },
        { x: -halfW, y: yTop + slopeTilt, z: halfW },
      ];
      const botCorners: Vec3[] = [
        { x: -halfW, y: yBot, z: -halfW },
        { x: halfW, y: yBot, z: -halfW },
        { x: halfW, y: yBot, z: halfW },
        { x: -halfW, y: yBot, z: halfW },
      ];

      const pTop = topCorners.map((v) => project(v, cx, cy, scale, cosY, sinY, cosP, sinP)) as [
        ProjectedPt,
        ProjectedPt,
        ProjectedPt,
        ProjectedPt,
      ];
      const pBot = botCorners.map((v) => project(v, cx, cy, scale, cosY, sinY, cosP, sinP)) as [
        ProjectedPt,
        ProjectedPt,
        ProjectedPt,
        ProjectedPt,
      ];

      // Determine visible side faces by face center depth (painter's order back-to-front)
      const faces: Array<{
        pts: [ProjectedPt, ProjectedPt, ProjectedPt, ProjectedPt];
        zMean: number;
        fill: string;
      }> = [
        {
          pts: [pTop[0], pTop[1], pBot[1], pBot[0]],
          zMean: (pTop[0].z + pTop[1].z + pBot[1].z + pBot[0].z) / 4,
          fill: colors.left,
        },
        {
          pts: [pTop[1], pTop[2], pBot[2], pBot[1]],
          zMean: (pTop[1].z + pTop[2].z + pBot[2].z + pBot[1].z) / 4,
          fill: colors.right,
        },
        {
          pts: [pTop[2], pTop[3], pBot[3], pBot[2]],
          zMean: (pTop[2].z + pTop[3].z + pBot[3].z + pBot[2].z) / 4,
          fill: colors.left,
        },
        {
          pts: [pTop[3], pTop[0], pBot[0], pBot[3]],
          zMean: (pTop[3].z + pTop[0].z + pBot[0].z + pBot[3].z) / 4,
          fill: colors.right,
        },
      ];

      // Sort farthest (highest z) first
      faces.sort((a, b) => b.zMean - a.zMean);

      // Draw visible front-most 2 side faces last
      for (const f of faces) {
        drawQuad(ctx, f.pts, f.fill, colors.stroke, 1);
      }

      // Draw top face
      drawQuad(ctx, pTop, colors.top, colors.stroke, 1.2);

      return { pTop, pBot };
    };

    const renderFrame = (now: number) => {
      const t = (now - startTime) * 0.001;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const w = canvas.width;
      const h = canvas.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      ctx.clearRect(0, 0, w, h);

      // Smooth interpolation for exploded & regime transitions
      const targetExplode = exploded ? 1 : 0;
      explodeAnimRef.current += (targetExplode - explodeAnimRef.current) * 0.14;
      const exp = explodeAnimRef.current;

      const targetRegime = regime === "recommended" ? 1 : 0;
      regimeAnimRef.current += (targetRegime - regimeAnimRef.current) * 0.12;
      const reg = regimeAnimRef.current; // 0 = baseline, 1 = recommended

      const isDark = document.documentElement.classList.contains("dark");

      const cx = w * 0.44;
      const cy = h * 0.52;
      const baseScale = Math.min(w, h) * 0.21;

      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const cosP = Math.cos(pitch);
      const sinP = Math.sin(pitch);

      // Subtle background technical polar grid on floor plane
      const floorY = -1.35 - exp * 0.35;
      ctx.save();
      const gridStep = 0.45;
      ctx.strokeStyle = isDark ? "rgba(228, 224, 212, 0.06)" : "rgba(20, 24, 21, 0.07)";
      ctx.lineWidth = 1 * dpr;
      for (let i = -3; i <= 3; i++) {
        const a = project({ x: i * gridStep, y: floorY, z: -1.35 }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        const b = project({ x: i * gridStep, y: floorY, z: 1.35 }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();

        const c = project({ x: -1.35, y: floorY, z: i * gridStep }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        const d = project({ x: 1.35, y: floorY, z: i * gridStep }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        ctx.beginPath();
        ctx.moveTo(c.x, c.y);
        ctx.lineTo(d.x, d.y);
        ctx.stroke();
      }
      ctx.restore();

      // Layer vertical bounds (bottom-to-top painter's order!)
      const gap = exp * 0.26;

      // -----------------------------------------------------------------------
      // LAYER 1 (Bottom): Deep Aquifer Horizon (>100 cm, NASA GRACE-FO)
      // -----------------------------------------------------------------------
      const aqBot = -1.25 - gap * 1.3;
      const isDepleting = gwTrend < -0.5;
      // In baseline, water table is lower if depleting; in recommended, water table is conserved higher
      const waterLevelBoost = isDepleting ? reg * 0.14 : 0.05;
      const aqTop = -0.78 - gap * 1.3 + waterLevelBoost + Math.sin(t * 2.1) * 0.015;

      const aqSlab = drawSlab(
        ctx,
        cx,
        cy,
        baseScale,
        cosY,
        sinY,
        cosP,
        sinP,
        aqTop,
        aqBot,
        0,
        {
          top: reg > 0.5 ? "rgba(56, 152, 200, 0.72)" : isDepleting ? "rgba(217, 78, 52, 0.55)" : "rgba(56, 152, 200, 0.65)",
          left: reg > 0.5 ? "rgba(29, 111, 165, 0.68)" : isDepleting ? "rgba(180, 55, 38, 0.50)" : "rgba(29, 111, 165, 0.60)",
          right: reg > 0.5 ? "rgba(20, 86, 130, 0.76)" : isDepleting ? "rgba(140, 42, 30, 0.58)" : "rgba(20, 86, 130, 0.68)",
          stroke: reg > 0.5 ? "rgba(125, 211, 252, 0.55)" : "rgba(251, 146, 60, 0.5)",
        }
      );

      // Draw animated groundwater wave lines across Aquifer top
      ctx.save();
      ctx.strokeStyle = "rgba(224, 242, 254, 0.45)";
      ctx.lineWidth = 1.1 * dpr;
      for (let zLine = -0.8; zLine <= 0.8; zLine += 0.4) {
        ctx.beginPath();
        for (let s = 0; s <= 12; s++) {
          const xPos = -0.95 + (s / 12) * 1.9;
          const waveY = aqTop + Math.sin(t * 2.6 + xPos * 3 + zLine * 2) * 0.02;
          const pt = project({ x: xPos, y: waveY, z: zLine }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
          if (s === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();
      }
      ctx.restore();

      // -----------------------------------------------------------------------
      // LAYER 2 (Middle-Low): Subsoil Root Zone (30–100 cm, NASA SMAP L4)
      // -----------------------------------------------------------------------
      const rzBot = -0.62 - gap * 0.4;
      const rzTop = -0.05 - gap * 0.4;
      const smapNorm = Math.max(0.1, Math.min(1, currentSmap / 100));

      // Interpolate subsoil color between dry terracotta-ochre and moist dark hydro-loam
      const rzTopColor = `rgba(${Math.round(158 - smapNorm * 70)}, ${Math.round(108 + smapNorm * 22)}, ${Math.round(74 + smapNorm * 65)}, 0.86)`;
      const rzLeftColor = `rgba(${Math.round(136 - smapNorm * 65)}, ${Math.round(92 + smapNorm * 18)}, ${Math.round(62 + smapNorm * 58)}, 0.88)`;
      const rzRightColor = `rgba(${Math.round(112 - smapNorm * 55)}, ${Math.round(76 + smapNorm * 15)}, ${Math.round(52 + smapNorm * 48)}, 0.92)`;

      const rzSlab = drawSlab(
        ctx,
        cx,
        cy,
        baseScale,
        cosY,
        sinY,
        cosP,
        sinP,
        rzTop,
        rzBot,
        0,
        {
          top: rzTopColor,
          left: rzLeftColor,
          right: rzRightColor,
          stroke: "rgba(186, 230, 253, 0.32)",
        }
      );

      // Moisture percolation droplets inside SMAP root-zone
      ctx.save();
      const numDrops = Math.round(6 + smapNorm * 14);
      ctx.fillStyle = "rgba(125, 211, 252, 0.65)";
      for (let i = 0; i < numDrops; i++) {
        const seedX = Math.sin(i * 17.3) * 0.82;
        const seedZ = Math.cos(i * 23.1) * 0.82;
        const dropProgress = ((t * 0.45 + i * 0.19) % 1);
        const dropY = rzTop - dropProgress * (rzTop - rzBot);
        const dp = project({ x: seedX, y: dropY, z: seedZ }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        ctx.beginPath();
        ctx.arc(dp.x, dp.y, 2.2 * dpr * dp.scale, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // -----------------------------------------------------------------------
      // LAYER 3 (Middle-High): Topsoil Horizon A (0–30 cm, ISRIC SoilGrids + RothC)
      // -----------------------------------------------------------------------
      const tsBot = 0.08 + gap * 0.45;
      const tsTop = 0.56 + gap * 0.45;
      const slopeTilt = Math.min(0.14, (slopePct / 12) * 0.14);

      // Darker, richer humus tone when SOC is higher or under Recommended Strategy
      const socRichness = Math.min(1, (soc + reg * 3.5) / 18);
      const tsTopR = Math.round(138 - socRichness * 58);
      const tsTopG = Math.round(92 - socRichness * 34);
      const tsTopB = Math.round(64 - socRichness * 26);

      const tsSlab = drawSlab(
        ctx,
        cx,
        cy,
        baseScale,
        cosY,
        sinY,
        cosP,
        sinP,
        tsTop,
        tsBot,
        slopeTilt,
        {
          top: `rgba(${tsTopR}, ${tsTopG}, ${tsTopB}, 0.94)`,
          left: `rgba(${Math.max(28, tsTopR - 18)}, ${Math.max(20, tsTopG - 14)}, ${Math.max(14, tsTopB - 10)}, 0.95)`,
          right: `rgba(${Math.max(22, tsTopR - 32)}, ${Math.max(15, tsTopG - 24)}, ${Math.max(10, tsTopB - 18)}, 0.97)`,
          stroke: "rgba(217, 119, 70, 0.45)",
        }
      );

      // Soil texture granulation particles (Sand / Silt / Clay strata markers on front faces)
      ctx.save();
      for (let i = 0; i < 28; i++) {
        const gx = Math.sin(i * 31.7) * 0.92;
        const gz = Math.cos(i * 19.3) * 0.92;
        const gy = tsBot + ((i % 7) / 7) * (tsTop - tsBot);
        const gpt = project({ x: gx, y: gy, z: gz }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
        ctx.fillStyle =
          i % 3 === 0
            ? "rgba(245, 158, 11, 0.38)" // Sand grain
            : i % 3 === 1
            ? "rgba(214, 211, 209, 0.28)" // Silt
            : "rgba(180, 83, 9, 0.35)"; // Clay platelet
        ctx.beginPath();
        ctx.arc(gpt.x, gpt.y, (1.4 + (i % 2) * 0.8) * dpr, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // -----------------------------------------------------------------------
      // LAYER 4: Surface Canopy, Ponding Water / Mulch, Roots & BNF Nodules
      // -----------------------------------------------------------------------
      // If baseline mode, render flooded paddy ponding sheet on top of topsoil
      if (reg < 0.85) {
        const pondAlpha = (1 - reg) * 0.42;
        const pondH = tsTop + 0.04;
        const pondCorners: Vec3[] = [
          { x: -1.02, y: pondH + slopeTilt, z: -1.02 },
          { x: 1.02, y: pondH - slopeTilt, z: -1.02 },
          { x: 1.02, y: pondH - slopeTilt, z: 1.02 },
          { x: -1.02, y: pondH + slopeTilt, z: 1.02 },
        ];
        const pPond = pondCorners.map((v) =>
          project(v, cx, cy, baseScale, cosY, sinY, cosP, sinP)
        ) as [ProjectedPt, ProjectedPt, ProjectedPt, ProjectedPt];
        drawQuad(ctx, pPond, `rgba(56, 189, 248, ${pondAlpha.toFixed(2)})`, "rgba(125, 211, 252, 0.45)", 1);
      } else {
        // Organic residue mulch strips on soil surface in Recommended mode
        ctx.save();
        ctx.strokeStyle = `rgba(212, 155, 53, ${(reg * 0.55).toFixed(2)})`;
        ctx.lineWidth = 2.2 * dpr;
        for (let r = -0.8; r <= 0.8; r += 0.32) {
          const m1 = project({ x: -0.92, y: tsTop + 0.015, z: r }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
          const m2 = project({ x: 0.92, y: tsTop + 0.015, z: r }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
          ctx.beginPath();
          ctx.moveTo(m1.x, m1.y);
          ctx.lineTo(m2.x, m2.y);
          ctx.stroke();
        }
        ctx.restore();
      }

      // Draw 3D Crop Rows + Root Architecture + Rhizobium N-fixation nodules
      const rowPositions = [-0.72, -0.24, 0.24, 0.72];
      for (let rIdx = 0; rIdx < rowPositions.length; rIdx++) {
        const zRow = rowPositions[rIdx];
        const isLegumeRow = reg > 0.5 && rIdx % 2 === 1;

        for (let cIdx = -3; cIdx <= 3; cIdx++) {
          const xPos = cIdx * 0.26;
          const localSlopeOffset = (-xPos / 1.05) * slopeTilt;
          const surfY = tsTop + localSlopeOffset;

          // Root depth: shallow in baseline (stays in topsoil), deep taproot in recommended (reaches SMAP root zone)
          const rootDepth = reg > 0.5 ? (isLegumeRow ? 0.58 : 0.42) : 0.22;
          const rootStart = project({ x: xPos, y: surfY - 0.02, z: zRow }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
          const rootEnd = project(
            { x: xPos + Math.sin(cIdx + rIdx) * 0.05, y: surfY - rootDepth, z: zRow },
            cx,
            cy,
            baseScale,
            cosY,
            sinY,
            cosP,
            sinP
          );

          ctx.save();
          ctx.strokeStyle = isLegumeRow ? "rgba(134, 239, 172, 0.65)" : "rgba(231, 229, 228, 0.42)";
          ctx.lineWidth = 1.3 * dpr;
          ctx.beginPath();
          ctx.moveTo(rootStart.x, rootStart.y);
          ctx.lineTo(rootEnd.x, rootEnd.y);
          ctx.stroke();

          // Symbiotic N-fixation nodules on legume roots in Recommended mode
          if (isLegumeRow) {
            const nodPt = project(
              { x: xPos + 0.03, y: surfY - rootDepth * 0.65, z: zRow },
              cx,
              cy,
              baseScale,
              cosY,
              sinY,
              cosP,
              sinP
            );
            ctx.fillStyle = "#52b778";
            ctx.beginPath();
            ctx.arc(nodPt.x, nodPt.y, 2.8 * dpr * nodPt.scale, 0, Math.PI * 2);
            ctx.fill();
          }
          ctx.restore();

          // Above-ground 3D crop stem & foliage
          const sway = Math.sin(t * 2.0 + xPos * 2 + zRow * 3) * 0.035;
          const stemH = isLegumeRow ? 0.26 : 0.36;
          const basePt = project({ x: xPos, y: surfY, z: zRow }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
          const tipPt = project(
            { x: xPos + sway, y: surfY + stemH, z: zRow },
            cx,
            cy,
            baseScale,
            cosY,
            sinY,
            cosP,
            sinP
          );
          const leafLeft = project(
            { x: xPos - 0.09 + sway * 0.6, y: surfY + stemH * 0.68, z: zRow + 0.04 },
            cx,
            cy,
            baseScale,
            cosY,
            sinY,
            cosP,
            sinP
          );
          const leafRight = project(
            { x: xPos + 0.09 + sway * 0.6, y: surfY + stemH * 0.72, z: zRow - 0.04 },
            cx,
            cy,
            baseScale,
            cosY,
            sinY,
            cosP,
            sinP
          );

          ctx.save();
          // In Baseline mode with FIRMS residue burning in post-Rabi (Apr/May) or post-Kharif (Oct/Nov), show charred stubble
          const isFireView =
            reg < 0.5 &&
            hazards.residue_burning_detected &&
            (monthIdx === 3 || monthIdx === 4 || monthIdx === 9 || monthIdx === 10);
          ctx.strokeStyle = isFireView
            ? "#ea580c"
            : isLegumeRow
            ? "#34d399"
            : reg > 0.5
            ? "#65a30d"
            : "#84cc16";
          ctx.lineWidth = 2.1 * dpr * basePt.scale;
          ctx.lineCap = "round";

          ctx.beginPath();
          ctx.moveTo(basePt.x, basePt.y);
          ctx.lineTo(tipPt.x, tipPt.y);
          ctx.moveTo(basePt.x + (tipPt.x - basePt.x) * 0.45, basePt.y + (tipPt.y - basePt.y) * 0.45);
          ctx.lineTo(leafLeft.x, leafLeft.y);
          ctx.moveTo(basePt.x + (tipPt.x - basePt.x) * 0.55, basePt.y + (tipPt.y - basePt.y) * 0.55);
          ctx.lineTo(leafRight.x, leafRight.y);
          ctx.stroke();

          // Canopy grain/pod crown
          ctx.fillStyle = isFireView
            ? "#ef4444"
            : isLegumeRow
            ? "#5fae7b"
            : "#eab308";
          ctx.beginPath();
          ctx.arc(tipPt.x, tipPt.y, 2.8 * dpr * tipPt.scale, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }
      }

      // -----------------------------------------------------------------------
      // LAYER 5 (Top): NASA Orbital Sensor Swath Plane (SMAP / HLS / GRACE-FO)
      // -----------------------------------------------------------------------
      const orbitY = 1.18 + gap * 1.15;
      const orbitCorners: Vec3[] = [
        { x: -1.05, y: orbitY, z: -1.05 },
        { x: 1.05, y: orbitY, z: -1.05 },
        { x: 1.05, y: orbitY, z: 1.05 },
        { x: -1.05, y: orbitY, z: 1.05 },
      ];
      const pOrbit = orbitCorners.map((v) =>
        project(v, cx, cy, baseScale, cosY, sinY, cosP, sinP)
      ) as [ProjectedPt, ProjectedPt, ProjectedPt, ProjectedPt];

      drawQuad(
        ctx,
        pOrbit,
        isDark ? "rgba(82, 183, 120, 0.07)" : "rgba(46, 111, 64, 0.06)",
        isDark ? "rgba(82, 183, 120, 0.38)" : "rgba(46, 111, 64, 0.35)",
        1.1 * dpr
      );

      // Scanning laser line sweeping across the orbital plane and projecting onto canopy
      const scanZ = Math.sin(t * 1.15) * 0.92;
      const scanL = project({ x: -1.05, y: orbitY, z: scanZ }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
      const scanR = project({ x: 1.05, y: orbitY, z: scanZ }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
      const surfL = project({ x: -1.05, y: tsTop, z: scanZ }, cx, cy, baseScale, cosY, sinY, cosP, sinP);
      const surfR = project({ x: 1.05, y: tsTop, z: scanZ }, cx, cy, baseScale, cosY, sinY, cosP, sinP);

      ctx.save();
      drawQuad(
        ctx,
        [scanL, scanR, surfR, surfL],
        isDark ? "rgba(56, 189, 248, 0.08)" : "rgba(29, 111, 165, 0.07)"
      );
      ctx.strokeStyle = isDark ? "rgba(56, 189, 248, 0.75)" : "rgba(29, 111, 165, 0.7)";
      ctx.lineWidth = 1.6 * dpr;
      ctx.beginPath();
      ctx.moveTo(scanL.x, scanL.y);
      ctx.lineTo(scanR.x, scanR.y);
      ctx.stroke();
      ctx.restore();

      // -----------------------------------------------------------------------
      // Technical Callout Leader Lines & Stratigraphic Annotations (Right Side)
      // -----------------------------------------------------------------------
      if (w >= 520) {
        const callouts = [
          {
            anchor: pOrbit[1],
            tag: "ORBITAL // HLS · SMAP · GRACE",
            val: `${MONTHS[monthIdx]} Rain ${Math.round(monthlyRain)} mm`,
            color: isDark ? "#52b778" : "#2e6f40",
          },
          {
            anchor: tsSlab.pTop[1],
            tag: "HORIZON A // 0–30 cm TOPSOIL",
            val: `SOC ${soc.toFixed(1)} g/kg · ${reg > 0.5 ? `+${socDeltaTop.toFixed(1)}` : socDeltaBase.toFixed(1)} t C/ha`,
            color: isDark ? "#d97746" : "#b85d35",
          },
          {
            anchor: rzSlab.pTop[1],
            tag: "HORIZON B // 30–100 cm ROOT ZONE",
            val: `SMAP Moisture ${Math.round(currentSmap)}th %ile`,
            color: isDark ? "#4da8da" : "#1d6fa5",
          },
          {
            anchor: aqSlab.pTop[1],
            tag: "HORIZON C // >100 cm AQUIFER",
            val:
              reg > 0.5
                ? `Saved ${savedWaterPct}% Irrig (${gwTrend.toFixed(1)} cm/yr)`
                : `GRACE Drawdown ${gwTrend.toFixed(2)} cm/yr`,
            color: reg > 0.5 ? (isDark ? "#4da8da" : "#1d6fa5") : "#e11d48",
          },
        ];

        const labelX = Math.min(w - 16 * dpr, cx + baseScale * 1.48);
        ctx.save();
        ctx.font = `600 ${Math.round(10 * dpr)}px var(--font-geist-mono), monospace`;

        callouts.forEach((c) => {
          const ax = c.anchor.x;
          const ay = c.anchor.y;
          const elbowX = ax + 24 * dpr;

          // Leader line
          ctx.strokeStyle = isDark ? "rgba(228, 224, 212, 0.28)" : "rgba(20, 24, 21, 0.28)";
          ctx.lineWidth = 1 * dpr;
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(elbowX, ay - 8 * dpr);
          ctx.lineTo(labelX, ay - 8 * dpr);
          ctx.stroke();

          // Anchor dot
          ctx.fillStyle = c.color;
          ctx.beginPath();
          ctx.arc(ax, ay, 3 * dpr, 0, Math.PI * 2);
          ctx.fill();

          // Text readout
          ctx.fillStyle = isDark ? "rgba(236, 234, 223, 0.62)" : "rgba(20, 24, 21, 0.62)";
          ctx.font = `600 ${Math.round(9.5 * dpr)}px var(--font-geist-mono), monospace`;
          ctx.fillText(c.tag, elbowX + 6 * dpr, ay - 22 * dpr);

          ctx.fillStyle = isDark ? "#eceadf" : "#141815";
          ctx.font = `700 ${Math.round(11 * dpr)}px var(--font-geist-mono), monospace`;
          ctx.fillText(c.val, elbowX + 6 * dpr, ay - 11 * dpr);
        });
        ctx.restore();
      }

      rafId = window.requestAnimationFrame(renderFrame);
    };

    rafId = window.requestAnimationFrame(renderFrame);
    return () => window.cancelAnimationFrame(rafId);
  }, [
    yaw,
    pitch,
    exploded,
    regime,
    monthIdx,
    sand,
    silt,
    clay,
    soc,
    slopePct,
    gwTrend,
    currentSmap,
    monthlyRain,
    savedWaterPct,
    socDeltaBase,
    socDeltaTop,
    hazards.residue_burning_detected,
  ]);

  // Pointer drag handlers for 3D orbit
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    lastPointerRef.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastPointerRef.current.x;
    const dy = e.clientY - lastPointerRef.current.y;
    lastPointerRef.current = { x: e.clientX, y: e.clientY };

    setYaw((prev) => prev + dx * 0.009);
    setPitch((prev) => Math.max(0.18, Math.min(1.05, prev + dy * 0.007)));
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  };

  const resetCamera = () => {
    setYaw(-0.68);
    setPitch(0.48);
    setExploded(true);
  };

  // Combine provenance from soil and water for full transparency
  const combinedProvenance = [...(soil.provenance ?? []), ...(water.provenance ?? [])];

  return (
    <section
      aria-label="3D Stratigraphic Soil & Aquifer Monolith"
      className="glass rounded-2xl border border-line overflow-hidden reticle-frame"
    >
      {/* Instrument Header Bar */}
      <div className="instrument-header px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded bg-foreground/8 text-foreground border border-line">
            FIG. 01 // {t("soil3d.figTag")}
          </span>
          <h3 className="font-display font-bold text-sm text-foreground">
            {t("soil3d.title")}
          </h3>
        </div>

        {/* Regime Switcher: Baseline vs Recommended Strategy */}
        <div className="flex items-center gap-2 flex-wrap">
          <div
            role="group"
            aria-label={t("soil3d.regimeAria")}
            className="inline-flex rounded-lg bg-background/80 p-0.5 border border-line text-[11px] font-mono"
          >
            <button
              type="button"
              onClick={() => setRegime("baseline")}
              className={`px-2.5 py-1 rounded-md font-semibold transition-all cursor-pointer ${
                regime === "baseline"
                  ? "bg-rose-500/15 text-rose-600 dark:text-rose-300 border border-rose-500/30"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {t("soil3d.baselinePractice")}
            </button>
            <button
              type="button"
              onClick={() => setRegime("recommended")}
              className={`px-2.5 py-1 rounded-md font-semibold transition-all cursor-pointer ${
                regime === "recommended"
                  ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {t("soil3d.regenStrategy")}
            </button>
          </div>

          <button
            type="button"
            onClick={() => setExploded((v) => !v)}
            className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono font-semibold flex items-center gap-1.5 cursor-pointer transition-colors ${
              exploded
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-line bg-surface text-muted hover:text-foreground"
            }`}
            title={t("soil3d.explodeTitle")}
          >
            <ArrowDownUp className="w-3 h-3" />
            <span>{exploded ? t("soil3d.exploded") : t("soil3d.compact")}</span>
          </button>

          <button
            type="button"
            onClick={resetCamera}
            className="p-1.5 rounded-lg border border-line bg-surface text-muted hover:text-foreground cursor-pointer transition-colors"
            title={t("soil3d.resetTitle")}
            aria-label={t("soil3d.resetTitle")}
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 3D Interactive Canvas Viewport */}
      <div className="relative w-full h-[360px] sm:h-[400px] select-none">
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className="w-full h-full cursor-grab active:cursor-grabbing block touch-none"
        />

        {/* Top-left Telemetry Overlay Pill */}
        <div className="absolute top-3 left-3.5 pointer-events-none space-y-1.5">
          <div className="glass-strong px-3 py-1.5 rounded-lg border border-line text-[11px] font-mono flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-emerald-500" />
            <span className="text-muted">{t("soil3d.orbitLabel")}:</span>
            <span className="text-foreground font-semibold">
              {t("soil3d.dragRotate")} · {slopePct.toFixed(1)}% {t("soil3d.slopeSuffix")}
            </span>
          </div>

          <div className="glass-strong px-3 py-1.5 rounded-lg border border-line text-[11px] font-mono flex items-center gap-3">
            <span>
              {t("soil3d.textureLabel")}: <strong className="text-foreground capitalize">{soil.texture_class ?? "Loam"}</strong>
            </span>
            <span className="text-muted">|</span>
            <span>
              {t("soil3d.sand")} <strong className="text-amber-500">{Math.round(sand)}%</strong> · {t("soil3d.silt")}{" "}
              <strong className="text-stone-400">{Math.round(silt)}%</strong> · {t("soil3d.clay")}{" "}
              <strong className="text-orange-500">{Math.round(clay)}%</strong>
            </span>
          </div>
        </div>

        {/* Accessible screen-reader data table fallback */}
        <table className="sr-only">
          <caption>Stratigraphic Soil and Subsurface Water Profile for {profile.field.name ?? "Selected Parcel"}</caption>
          <thead>
            <tr>
              <th>Horizon Layer</th>
              <th>Depth</th>
              <th>Metric</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Topsoil Horizon A</td>
              <td>0 to 30 cm</td>
              <td>Soil Organic Carbon &amp; Texture</td>
              <td>
                {soc.toFixed(1)} g/kg, {soil.texture_class ?? "Loam"} ({Math.round(sand)}% sand, {Math.round(silt)}% silt,{" "}
                {Math.round(clay)}% clay)
              </td>
            </tr>
            <tr>
              <td>Root Zone Horizon B</td>
              <td>30 to 100 cm</td>
              <td>SMAP Root-Zone Soil Moisture ({MONTHS[monthIdx]})</td>
              <td>{Math.round(currentSmap)}th percentile</td>
            </tr>
            <tr>
              <td>Deep Aquifer Horizon C</td>
              <td>Below 100 cm</td>
              <td>GRACE-FO Groundwater Trend</td>
              <td>{gwTrend.toFixed(2)} cm/yr</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Bottom Seasonal Hydrology Scrubber & Provenance Bar */}
      <div className="px-5 py-3.5 border-t border-line bg-surface-strong/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 flex-1">
          <button
            type="button"
            onClick={() => setAutoPlay((v) => !v)}
            className="p-1.5 rounded-lg border border-line bg-surface hover:bg-foreground/5 text-foreground cursor-pointer transition-colors shrink-0"
            title={autoPlay ? t("soil3d.pauseCycle") : t("soil3d.playCycle")}
            aria-label={autoPlay ? t("soil3d.pauseCycle") : t("soil3d.playCycle")}
          >
            {autoPlay ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>

          <div className="flex-1 space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-muted uppercase tracking-wider flex items-center gap-1">
                <SlidersHorizontal className="w-3 h-3" />
                <span>{t("soil3d.smapFront")}:</span>
                <strong className="text-foreground">{MONTHS[monthIdx]}</strong>
                <span className="text-[8px] px-1 rounded bg-foreground/10 text-muted font-mono uppercase tracking-wider">
                  {t("badge.contextOnly")}
                </span>
              </span>
              <span className="text-sky-600 dark:text-sky-400 font-bold">
                {t("soil3d.rootZone")}: {Math.round(currentSmap)}th %ile · {t("soil3d.rain")}: {Math.round(monthlyRain)} mm
              </span>
            </div>

            <div className="grid grid-cols-12 gap-1">
              {MONTHS.map((m, idx) => {
                const active = idx === monthIdx;
                const pct = smapArray[idx] ?? 50;
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => {
                      setAutoPlay(false);
                      setMonthIdx(idx);
                    }}
                    className={`py-1 rounded text-[9px] font-mono font-bold transition-all cursor-pointer border ${
                      active
                        ? "bg-sky-500/20 text-sky-600 dark:text-sky-300 border-sky-500/50"
                        : "bg-foreground/4 text-muted border-transparent hover:border-line hover:text-foreground"
                    }`}
                    title={`${m}: SMAP ${Math.round(pct)}th percentile`}
                  >
                    {m[0]}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="shrink-0">
          <ProvenanceChip provenance={combinedProvenance} />
        </div>
      </div>
    </section>
  );
}
