"use client"
import { useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api/client"
import { OperationsOverview, BinOperation } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { tone, bySeverity, needsAttention } from "@/lib/ops"
import { WasteBin } from "@/components/ui/waste-bin"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { ArrowRight, Info, ShieldCheck, Loader2, AlertTriangle } from "lucide-react"
import { useRouter } from "next/navigation"

function CapacityBar({ percent, barClass }: { percent: number; barClass: string }) {
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={`h-full rounded-full transition-all duration-700 ${barClass}`}
        style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
      />
    </div>
  )
}

export default function OperationsPage() {
  const [data, setData] = useState<OperationsOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedBin, setSelectedBin] = useState<BinOperation | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [startingId, setStartingId] = useState<string | null>(null)
  const router = useRouter()

  useEffect(() => {
    let mounted = true
    const fetchOps = async () => {
      try {
        const result = await api.operations()
        if (mounted) { setData(result.operations); setError(null) }
      } catch (err: any) {
        if (mounted) setError(err.message || "Failed to reach the operations service.")
      }
    }
    fetchOps()
    const interval = setInterval(fetchOps, 10000)
    return () => { mounted = false; clearInterval(interval) }
  }, [])

  const sorted = useMemo(() => (data ? [...data.bins].sort(bySeverity) : []), [data])
  // The banner highlights the single most urgent stream: an in-progress
  // collection first, otherwise the highest-severity bin that needs attention.
  // Every bin card remains independently actionable regardless of this choice.
  const priority = sorted.find((b) => b.active_job)
    || sorted.find((b) => needsAttention(b.fill_status))
    || null

  const handleContinue = (bin: BinOperation) => {
    if (bin.active_job) router.push(`/disposal/job/${bin.active_job.job_id}`)
  }

  const handleStartDisposal = async (bin: BinOperation) => {
    setNotice(null)
    // If a collection is already running for this bin, resume it rather than
    // starting a new one (backend also enforces one active job per bin).
    if (bin.active_job) {
      router.push(`/disposal/job/${bin.active_job.job_id}`)
      return
    }
    // A collection job operates on the BIN (a snapshot of its routed audit
    // events) — never an arbitrary single event. The backend is the source of
    // truth for eligibility and workflow state.
    if (bin.pending_collection_count <= 0) {
      setNotice(
        `${bin.label} shows high capacity but has no routed item records available to collect. Nothing to dispose.`
      )
      return
    }
    setStartingId(bin.bin_id)
    try {
      const res = await api.startCollectionJob(bin.bin_id)
      router.push(`/disposal/job/${res.job.job_id}`)
    } catch (err: any) {
      if (err?.code === "NO_ELIGIBLE_EVENTS") {
        setNotice(
          `No routed item records are available to collect for the ${bin.label} stream yet.`
        )
      } else {
        setNotice("Could not start collection — the operations service is unreachable.")
      }
    } finally {
      setStartingId(null)
    }
  }
  // MAIN_RENDER
  if (error) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-destructive" />
        <p className="mt-3 text-sm text-foreground">{error}</p>
        <p className="mt-1 text-xs text-muted-foreground">Make sure the MediWaste backend is running.</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-9 w-64 rounded bg-muted" />
        <div className="h-40 rounded-2xl bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-56 rounded-2xl bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Operations Center</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Hospital waste flow · Bin status · Collection readiness
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-warning/40 bg-warning/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-warning">
          <Info className="h-3.5 w-3.5" />
          Exhibition mode · Simulated capacity
        </span>
      </div>

      {notice && (
        <div className="rounded-xl border border-border bg-accent/60 px-4 py-3 text-sm text-foreground">
          {notice}
        </div>
      )}

      {priority ? (
        <PriorityBanner
          bin={priority}
          starting={startingId === priority.bin_id}
          onStart={() => handleStartDisposal(priority)}
        />
      ) : (
        <div className="flex items-center gap-3 rounded-2xl border border-success/30 bg-success/5 px-5 py-4">
          <ShieldCheck className="h-6 w-6 shrink-0 text-success" />
          <div>
            <p className="font-semibold text-foreground">All streams within normal capacity</p>
            <p className="text-sm text-muted-foreground">
              No bin currently requires collection. Monitoring {data.total_bins} waste streams.
            </p>
          </div>
        </div>
      )}

      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          All waste streams
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((bin) => (
            <BinCard
              key={bin.bin_id}
              bin={bin}
              onDetails={() => setSelectedBin(bin)}
              onStart={() => handleStartDisposal(bin)}
              onContinue={() => handleContinue(bin)}
              starting={startingId === bin.bin_id}
            />
          ))}
        </div>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">{data.disclaimer}</p>

      <BinDetailSheet bin={selectedBin} onClose={() => setSelectedBin(null)} />
    </div>
  )
}

function PriorityBanner({
  bin,
  starting,
  onStart,
}: {
  bin: BinOperation
  starting: boolean
  onStart: () => void
}) {
  const meta = resolveStream(bin.route_code, undefined)
  const t = tone(bin.fill_status)
  const hex = bin.hex || meta.hex
  const hasPending = bin.pending_collection_count > 0
  return (
    <div className={`relative overflow-hidden rounded-2xl border ${t.border} ${t.bg} p-5 shadow-card sm:p-6`}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-5">
          <WasteBin hex={hex} label={bin.label} size="lg" />
          <div>
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${t.dot} ${bin.fill_status === "CRITICAL" ? "animate-pulse-soft" : ""}`} />
              <span className={`text-xs font-bold uppercase tracking-widest ${t.text}`}>{bin.fill_status}</span>
            </div>
            <div className="mt-1 text-2xl font-bold tracking-tight text-foreground">
              {bin.label} · {bin.category}
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-5xl font-black tabular-nums text-foreground">{bin.fill_percent}%</span>
              <span className="text-sm font-medium text-muted-foreground">capacity</span>
            </div>
          </div>
        </div>

        <div className="flex-1 sm:pl-6">
          <div className="max-w-sm">
            <CapacityBar percent={bin.fill_percent} barClass={t.bar} />
            {bin.active_job ? (
              <>
                <p className="mt-3 text-sm font-semibold uppercase tracking-wide text-primary">
                  Collection in progress
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {bin.active_job.item_count} item
                  {bin.active_job.item_count === 1 ? "" : "s"} · Step{" "}
                  {Math.min(bin.active_job.completed_count + 1, bin.active_job.total_steps)} of{" "}
                  {bin.active_job.total_steps}
                </p>
                <Button size="lg" onClick={onStart} disabled={starting} className="mt-4 w-full font-semibold sm:w-auto">
                  Continue disposal
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </>
            ) : (
              <>
                <p className={`mt-3 text-sm font-semibold uppercase tracking-wide ${t.text}`}>
                  {bin.fill_status === "CRITICAL" ? "Collection required" : "Approaching capacity"}
                </p>
                {hasPending ? (
                  <>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {bin.pending_collection_count} routed item
                      {bin.pending_collection_count === 1 ? "" : "s"} pending collection.
                    </p>
                    <Button size="lg" onClick={onStart} disabled={starting} className="mt-4 w-full font-semibold sm:w-auto">
                      {starting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      Start disposal
                      {!starting && <ArrowRight className="ml-2 h-4 w-4" />}
                    </Button>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">
                    No routed item records available to collect.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
// SUBCOMPONENTS_2
function BinCard({
  bin,
  onDetails,
  onStart,
  onContinue,
  starting,
}: {
  bin: BinOperation
  onDetails: () => void
  onStart: () => void
  onContinue: () => void
  starting: boolean
}) {
  const meta = resolveStream(bin.route_code, undefined)
  const t = tone(bin.fill_status)
  const hex = bin.hex || meta.hex
  // Actionability is driven by real routed content and job state — NOT by
  // capacity alone. A high-capacity bin with zero routed events offers nothing;
  // any bin with pending events can start; a bin with an active job continues.
  const active = bin.active_job || null
  const canCollect = !active && bin.pending_collection_count > 0
  const stepNow = active
    ? Math.min(active.completed_count + 1, active.total_steps)
    : 0
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-card p-5 shadow-soft transition-shadow hover:shadow-lift">
      <div className="flex items-start justify-between">
        <WasteBin hex={hex} label={bin.label} size="md" />
        <span className={`inline-flex items-center gap-1.5 rounded-full ${t.bg} px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${t.text}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
          {bin.fill_status}
        </span>
      </div>

      <div className="mt-4">
        <div className="text-base font-semibold text-foreground">{bin.label}</div>
        <div className="text-sm text-muted-foreground">{bin.category}</div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-3xl font-bold tabular-nums text-foreground">{bin.fill_percent}%</span>
          {bin.fill_status === "CRITICAL" && (
            <span className="text-[11px] font-bold uppercase tracking-wide text-destructive">Collection required</span>
          )}
        </div>
        <CapacityBar percent={bin.fill_percent} barClass={t.bar} />
      </div>

      {/* Collection state line — sourced entirely from backend job/pending data */}
      <div className="mt-3 min-h-[1.25rem] text-xs font-medium">
        {active ? (
          <span className="text-primary">
            In progress · {active.item_count} item{active.item_count === 1 ? "" : "s"} · Step {stepNow} of {active.total_steps}
          </span>
        ) : bin.pending_collection_count > 0 ? (
          <span className="text-muted-foreground">
            {bin.pending_collection_count} item{bin.pending_collection_count === 1 ? "" : "s"} pending collection
          </span>
        ) : (
          <span className="text-muted-foreground/70">No items pending collection</span>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2">
        {active ? (
          <Button
            size="sm"
            onClick={onContinue}
            className="flex-1 font-semibold"
          >
            Continue disposal
          </Button>
        ) : canCollect ? (
          <Button
            size="sm"
            variant={bin.fill_status === "CRITICAL" ? "destructive" : "default"}
            onClick={onStart}
            disabled={starting}
            className="flex-1 font-semibold"
          >
            {starting ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Start disposal
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={onDetails} className={active || canCollect ? "" : "flex-1"}>
          Details
        </Button>
      </div>
    </div>
  )
}

function BinDetailSheet({ bin, onClose }: { bin: BinOperation | null; onClose: () => void }) {
  const meta = bin ? resolveStream(bin.route_code, undefined) : null
  const t = bin ? tone(bin.fill_status) : null
  return (
    <Sheet open={!!bin} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-[440px]">
        {bin && meta && t && (
          <>
            <SheetHeader>
              <SheetTitle className="text-xl">{bin.label} bin</SheetTitle>
              <SheetDescription>{bin.category}</SheetDescription>
            </SheetHeader>

            <div className="mt-6 flex items-center gap-5">
              <WasteBin hex={bin.hex || meta.hex} label={bin.label} size="md" />
              <div>
                <div className="text-4xl font-black tabular-nums text-foreground">{bin.fill_percent}%</div>
                <span className={`mt-1 inline-flex items-center gap-1.5 rounded-full ${t.bg} px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${t.text}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
                  {bin.fill_status}
                </span>
              </div>
            </div>

            <div className="mt-4">
              <CapacityBar percent={bin.fill_percent} barClass={t.bar} />
            </div>

            {bin.description && (
              <p className="mt-5 text-sm leading-relaxed text-muted-foreground">{bin.description}</p>
            )}

            <dl className="mt-6 space-y-3 border-t border-border pt-5 text-sm">
              <Row label="Route" value={bin.route_code} />
              <Row label="Waste type" value={bin.category || "—"} />
              <Row label="Capacity units" value={String(bin.capacity_units)} />
              <Row label="Routed events (total)" value={String(bin.routed_event_count)} />
              <Row label="Pending collection" value={String(bin.pending_collection_count)} />
              <Row label="Active collection job" value={bin.active_job ? bin.active_job.job_id : "—"} />
              <Row label="Data source" value={bin.data_source} />
              <Row label="Sensing" value={bin.sensing} />
            </dl>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  )
}

