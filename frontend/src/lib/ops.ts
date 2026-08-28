/**
 * Presentation helpers for the Operations center. Pure display logic — all
 * capacity/status values still originate from the Flask backend (SIMULATED).
 */

export type FillStatus = "OK" | "MODERATE" | "HIGH" | "CRITICAL";

/** Semantic tone for a fill status. Route colour lives on the bin, NOT here —
 *  status uses the calm clinical semantic palette (green/amber/red). */
export const STATUS_TONE: Record<
  FillStatus,
  { label: string; text: string; bg: string; border: string; bar: string; dot: string }
> = {
  OK: {
    label: "Normal",
    text: "text-success",
    bg: "bg-success/10",
    border: "border-success/30",
    bar: "bg-success",
    dot: "bg-success",
  },
  MODERATE: {
    label: "Filling",
    text: "text-primary",
    bg: "bg-primary/10",
    border: "border-primary/25",
    bar: "bg-primary",
    dot: "bg-primary",
  },
  HIGH: {
    label: "Near full",
    text: "text-warning",
    bg: "bg-warning/10",
    border: "border-warning/40",
    bar: "bg-warning",
    dot: "bg-warning",
  },
  CRITICAL: {
    label: "Collection required",
    text: "text-destructive",
    bg: "bg-destructive/10",
    border: "border-destructive/40",
    bar: "bg-destructive",
    dot: "bg-destructive",
  },
};

const RANK: Record<FillStatus, number> = { CRITICAL: 0, HIGH: 1, MODERATE: 2, OK: 3 };

/** Sort bins most-urgent first; ties broken by higher fill percent. */
export function bySeverity<T extends { fill_status: string; fill_percent: number }>(
  a: T,
  b: T
): number {
  const ra = RANK[(a.fill_status as FillStatus)] ?? 9;
  const rb = RANK[(b.fill_status as FillStatus)] ?? 9;
  if (ra !== rb) return ra - rb;
  return b.fill_percent - a.fill_percent;
}

export function tone(status: string) {
  return STATUS_TONE[(status as FillStatus)] ?? STATUS_TONE.OK;
}

/** A bin needs operator attention when near-full or critical. */
export function needsAttention(status: string): boolean {
  return status === "HIGH" || status === "CRITICAL";
}
