"use client"

import { readableInk } from "@/lib/waste"

interface WasteBinProps {
  /** Authoritative stream colour from backend route_meta.hex */
  hex?: string;
  /** Short label rendered on the bin band (e.g. "RED", "YELLOW") */
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZES = {
  sm: { w: 64, h: 76 },
  md: { w: 104, h: 124 },
  lg: { w: 156, h: 186 },
}

/**
 * A physical-looking hospital pedal-bin illustration (pure SVG, no raster).
 * The body colour is driven entirely by the backend-provided `hex` so the
 * visual never diverges from the policy colour code.
 */
export function WasteBin({ hex = "#94a3b8", label, size = "md", className = "" }: WasteBinProps) {
  const { w, h } = SIZES[size]
  const ink = readableInk(hex)
  const bandInk = readableInk(hex)

  // Derive a subtle darker shade for the lid/edge without extra deps.
  const shade = (c: string, amt: number) => {
    const x = c.replace("#", "")
    if (x.length < 6) return c
    const clamp = (n: number) => Math.max(0, Math.min(255, n))
    const r = clamp(parseInt(x.slice(0, 2), 16) - amt)
    const g = clamp(parseInt(x.slice(2, 4), 16) - amt)
    const b = clamp(parseInt(x.slice(4, 6), 16) - amt)
    return `#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`
  }
  const lid = shade(hex, 22)

  return (
    <div className={`inline-flex flex-col items-center ${className}`}>
      <svg
        width={w}
        height={h}
        viewBox="0 0 104 124"
        fill="none"
        role="img"
        aria-label={label ? `${label} waste bin` : "waste bin"}
      >
        {/* lid */}
        <rect x="14" y="20" width="76" height="14" rx="4" fill={lid} />
        {/* handle */}
        <rect x="42" y="12" width="20" height="9" rx="4" fill={lid} />
        {/* body — trapezoid */}
        <path
          d="M20 36 H84 L79 112 a6 6 0 0 1 -6 5.6 H31 a6 6 0 0 1 -6 -5.6 Z"
          fill={hex}
          stroke={shade(hex, 40)}
          strokeWidth="1.5"
        />
        {/* ribs */}
        <path d="M36 44 L34 110" stroke={shade(hex, 34)} strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <path d="M68 44 L70 110" stroke={shade(hex, 34)} strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        {/* label band */}
        <rect x="28" y="62" width="48" height="24" rx="4" fill={bandInk === "#ffffff" ? "rgba(255,255,255,0.16)" : "rgba(15,23,42,0.10)"} />
        {label && (
          <text
            x="52"
            y="78"
            textAnchor="middle"
            fontSize="12"
            fontWeight="800"
            fill={ink}
            letterSpacing="0.5"
          >
            {label.length > 6 ? label.slice(0, 6) : label}
          </text>
        )}
      </svg>
    </div>
  )
}
