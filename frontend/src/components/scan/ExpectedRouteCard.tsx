import { AnalyzeResponse } from "@/lib/types/api"
import { WasteBin } from "@/components/ui/waste-bin"
import { resolveStream, readableInk } from "@/lib/waste"

/**
 * THE decision hero. On the verification screen this is the one element allowed
 * to dominate: the waste type the policy engine matched, and the bin it selected.
 *
 * Every value comes from the `/analyze` payload. The frontend does not derive,
 * override or re-rank a route.
 */
export function ExpectedRouteCard({ data }: { data: AnalyzeResponse }) {
  const { decision, route_meta } = data.analysis
  const route = decision?.expected_route || "UNKNOWN"
  const meta = resolveStream(route, route_meta)
  const wasteType = meta.category || decision?.waste_type || "Unclassified"

  return (
    <section
      aria-label="Recommended disposal route"
      className="overflow-hidden rounded-2xl border border-border bg-card shadow-card"
    >
      {/* A single thin band of stream colour — the stream is identified, not shouted. */}
      <div className="h-1.5 w-full" style={{ backgroundColor: meta.hex }} aria-hidden />

      <div className="flex items-center gap-5 p-6 sm:gap-7 sm:p-7">
        <WasteBin hex={meta.hex} label={meta.label} size="lg" className="shrink-0" />

        <div className="min-w-0">
          <div className="t-eyebrow">Dispose as</div>
          <h2 className="t-hero mt-1 break-words uppercase">{wasteType}</h2>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center rounded-full px-3 py-1 text-sm font-bold"
              style={{ backgroundColor: meta.hex, color: readableInk(meta.hex) }}
            >
              {meta.label} bin
            </span>
            <span className="text-sm font-semibold text-muted-foreground">{route}</span>
          </div>

          <p className="t-meta mt-3">
            Selected by policy {decision?.rule_id}
            {decision?.policy_version ? ` · v${decision.policy_version}` : ""}
          </p>
        </div>
      </div>
    </section>
  )
}
