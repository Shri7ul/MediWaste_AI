import { RouteMeta } from "@/lib/types/api";

/**
 * Functional waste-stream swatches. These mirror policy_engine.STREAMS purely
 * for display fallbacks (legends, offline rendering). The AUTHORITATIVE colour,
 * label and category always come from the backend `route_meta` payload — this
 * map is only a graceful fallback and never drives a compliance decision.
 */
export const STREAM_FALLBACK: Record<string, RouteMeta> = {
  YELLOW: { hex: "#eab308", label: "Yellow", category: "Infectious" },
  RED: { hex: "#ef4444", label: "Red", category: "Sharps" },
  BLUE: { hex: "#3b82f6", label: "Blue", category: "Recyclable" },
  WHITE: { hex: "#e5e7eb", label: "White", category: "Chemical" },
  BROWN: { hex: "#a16207", label: "Brown", category: "Pharmaceutical" },
  BLACK: { hex: "#1f2937", label: "Black", category: "General" },
  RADIOACTIVE_STORAGE: { hex: "#d946ef", label: "Radioactive", category: "Radioactive" },
};

/** Resolve stream metadata, preferring backend-provided route_meta. */
export function resolveStream(
  code: string | null | undefined,
  routeMeta?: Record<string, RouteMeta>
): RouteMeta {
  if (!code) return { hex: "#94a3b8", label: "Unknown", category: "" };
  return (
    routeMeta?.[code] ||
    STREAM_FALLBACK[code] || { hex: "#94a3b8", label: code, category: "" }
  );
}

/** Pick a readable ink colour (dark vs white) for text placed on `hex`. */
export function readableInk(hex: string): string {
  const h = hex.replace("#", "");
  if (h.length < 6) return "#0f172a";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  // Perceived luminance
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.62 ? "#0f172a" : "#ffffff";
}

export const FILL_STATUS_META: Record<
  string,
  { label: string; tone: "ok" | "moderate" | "high" | "critical" }
> = {
  OK: { label: "Normal", tone: "ok" },
  MODERATE: { label: "Filling", tone: "moderate" },
  HIGH: { label: "Near full", tone: "high" },
  CRITICAL: { label: "Collection required", tone: "critical" },
};
