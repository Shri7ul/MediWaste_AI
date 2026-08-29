/**
 * The judge-facing product narrative:
 *
 *   SCAN → DECIDE → VERIFY → ACT → COLLECT → PROVE
 *
 * This is presentation only. Every stage is a label for work the BACKEND
 * already performs — nothing here decides, derives or stores anything. The rail
 * exists so an observer can place whatever screen they are looking at inside the
 * whole story within a couple of seconds.
 */

export const STAGES = [
  { id: "scan", label: "Scan", hint: "Capture the item" },
  { id: "decide", label: "Decide", hint: "Policy selects the route" },
  { id: "verify", label: "Verify", hint: "Operator confirms the bin" },
  { id: "act", label: "Act", hint: "Bin status and readiness" },
  { id: "collect", label: "Collect", hint: "Run the disposal workflow" },
  { id: "prove", label: "Prove", hint: "Permanent audit trail" },
] as const;

export type StageId = (typeof STAGES)[number]["id"];

export const STAGE_ORDER: StageId[] = STAGES.map((s) => s.id);

export function stageIndex(id: StageId | null): number {
  return id ? STAGE_ORDER.indexOf(id) : -1;
}

/** Coarse stage for a route. The scan flow refines this as the operator moves. */
export function stageForPath(pathname: string): StageId | null {
  if (pathname.startsWith("/disposal")) return "collect";
  if (pathname.startsWith("/operations")) return "act";
  if (pathname.startsWith("/events")) return "prove";
  if (pathname.startsWith("/dashboard")) return "prove";
  if (pathname.startsWith("/scan") || pathname === "/") return "scan";
  return null;
}
