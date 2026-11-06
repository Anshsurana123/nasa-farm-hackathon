"use client";

import { useEffect, useRef, type ReactNode } from "react";

interface ProgressRingProps {
  value: number;
  max?: number;
  label: string;
  size?: string;
  thickness?: string;
  color?: string;
  children?: ReactNode;
}

export function ProgressRing({
  value,
  max = 100,
  label,
  size = "3.5rem",
  thickness = "5px",
  color = "var(--accent-canopy)",
  children,
}: ProgressRingProps) {
  const progressRef = useRef<HTMLProgressElement | null>(null);
  const pct = Math.max(0, Math.min(100, Math.round((value / Math.max(1, max)) * 100)));

  useEffect(() => {
    const el = progressRef.current;
    if (!el) return;

    // Fallback for browsers that do not support CSS attr(value type(<number>))
    if (typeof CSS !== "undefined" && !CSS.supports("width: attr(value type(<number>))")) {
      el.style.setProperty("--value", String(pct));
      const observer = new MutationObserver(() => {
        el.style.setProperty("--value", el.getAttribute("value") ?? "0");
      });
      observer.observe(el, {
        attributes: true,
        attributeFilter: ["value"],
      });
      return () => observer.disconnect();
    }
  }, [pct]);

  return (
    <div className="progress-ring-wrapper shrink-0">
      <progress
        ref={progressRef}
        value={pct}
        max={100}
        aria-label={label}
        className="progress-ring"
        style={
          {
            "--size": size,
            "--thickness": thickness,
            "--fill-color": color,
            "--value": pct,
          } as React.CSSProperties
        }
      />
      {children && <div className="progress-ring-content">{children}</div>}
    </div>
  );
}
