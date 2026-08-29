"use client"
import { useCallback, useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api/client"
import { BinOperation, CollectionJob, RouteMeta, WorkflowStepState } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { WasteBin } from "@/components/ui/waste-bin"
import { Button } from "@/components/ui/button"
import { Check, ArrowRight, ArrowLeft, Loader2, AlertTriangle, ScanLine, FileText, ClipboardList, ChevronDown } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"

export default function CollectionJobPage({ params }: { params: { jobId: string } }) {
  const [job, setJob] = useState<CollectionJob | null>(null)
  const [routeMeta, setRouteMeta] = useState<Record<string, RouteMeta> | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await api.collectionJob(params.jobId)
      setJob(res.job)
      api.policy().then((p) => setRouteMeta(p.route_meta)).catch(() => {})
    } catch (e: any) {
      setLoadError(e instanceof ApiError && e.status === 404
        ? "This collection job could not be found."
        : e.message || "Failed to load the collection job.")
    }
  }, [params.jobId])

  useEffect(() => { load() }, [load])

  const handleComplete = async (stepId: string) => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.completeCollectionStep(params.jobId, stepId)
      if (res?.job) setJob(res.job)
      else await load()
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 409) {
        setError("This step can't be completed yet. Complete the previous step first.")
        await load()
      } else {
        setError(e?.message || "Couldn't record that step. Please try again.")
      }
    } finally {
      setSubmitting(false)
    }
  }
  // MAIN_RENDER
  if (loadError) {
    return (
      <div className="mx-auto mt-10 max-w-md rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-destructive" />
        <p className="mt-3 text-sm text-foreground">{loadError}</p>
        <Button asChild variant="outline" className="mt-4">
          <Link href="/operations">Back to operations</Link>
        </Button>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-2xl animate-pulse space-y-6 py-6">
        <div className="h-28 rounded-2xl bg-muted" />
        <div className="h-16 rounded-xl bg-muted" />
        <div className="h-52 rounded-2xl bg-muted" />
      </div>
    )
  }

  const meta = resolveStream(job.route_code, routeMeta)
  const streamLabel = job.waste_stream || meta.category || meta.label
  const wf = job.workflow
  const activeStep = wf.steps.find((s) => s.id === wf.current_step) || null
  const isComplete = job.status === "COMPLETED" || wf.is_complete

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-28 sm:pb-8">
      {/* Hero — a BIN collection cycle over multiple audit events. */}
      <div className="flex items-center gap-5 rounded-2xl border border-border bg-card p-5 shadow-soft">
        <WasteBin hex={meta.hex} label={meta.label} size="md" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-eyebrow">Collection workflow</span>
            {/* State is named, not just tinted. */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                isComplete
                  ? "bg-success/10 text-success"
                  : "bg-primary/10 text-primary"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${isComplete ? "bg-success" : "bg-primary animate-pulse-soft"}`} aria-hidden />
              {isComplete ? "Complete" : "In progress"}
            </span>
          </div>
          <h1 className="mt-1 t-display">
            {meta.label} · {streamLabel}
          </h1>
          <p className="text-sm text-muted-foreground">
            {job.event_count} routed item{job.event_count === 1 ? "" : "s"} in this collection
            {job.ward ? ` · ${job.ward}` : ""}
          </p>
          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground/70">
            Job {job.job_id}
          </p>
        </div>
      </div>

      <ProgressRail steps={wf.steps} currentId={wf.current_step} />

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <span>{error}</span>
        </div>
      )}

      <AnimatePresence mode="wait">
        {isComplete ? (
          <CompletionScreen key="done" job={job} meta={meta} streamLabel={streamLabel} />
        ) : activeStep ? (
          <ActiveStepCard
            key={activeStep.id}
            step={activeStep}
            index={wf.completed_count}
            total={wf.total_steps}
            submitting={submitting}
            onComplete={() => handleComplete(activeStep.id)}
          />
        ) : null}
      </AnimatePresence>

      <IncludedEvents job={job} />

      {wf.workflow_source && (
        <p className="text-[11px] leading-relaxed text-muted-foreground/70">
          Workflow provenance: {wf.workflow_source}
        </p>
      )}
    </div>
  )
}

function IncludedEvents({ job }: { job: CollectionJob }) {
  const [open, setOpen] = useState(false)
  const ids = job.event_ids || []
  return (
    <div id="included-events" className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-foreground">
          Included audit events · {job.event_count}
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <p className="mt-1 text-xs text-muted-foreground">
        Snapshot taken when this collection started. Each remains a permanent audit record.
      </p>
      {open && (
        <ul className="mt-4 space-y-2">
          {ids.length === 0 && (
            <li className="text-sm text-muted-foreground">No events referenced.</li>
          )}
          {ids.map((id) => (
            <li key={id}>
              <Link
                href={`/events?event=${id}`}
                className="flex items-center justify-between rounded-lg border border-border px-3 py-2 font-mono text-xs text-foreground transition-colors hover:bg-accent"
              >
                <span className="truncate">{id}</span>
                <ArrowRight className="ml-2 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ProgressRail({ steps, currentId }: { steps: WorkflowStepState[]; currentId: string | null }) {
  return (
    <div className="flex items-start justify-between">
      {steps.map((s, i) => {
        const done = s.status === "DONE"
        const current = s.id === currentId
        const last = i === steps.length - 1
        return (
          <div key={s.id} className="flex flex-1 flex-col items-center">
            <div className="flex w-full items-center">
              <div className="flex flex-1 justify-center">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors ${
                    done
                      ? "border-success bg-success text-white"
                      : current
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-muted-foreground/50"
                  }`}
                >
                  {done ? (
                    <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 18 }}>
                      <Check className="h-4 w-4" />
                    </motion.span>
                  ) : current ? (
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
                    </span>
                  ) : (
                    i + 1
                  )}
                </div>
              </div>
              {!last && (
                <div className={`h-0.5 flex-1 ${done ? "bg-success" : "bg-border"}`} />
              )}
            </div>
            <span
              className={`mt-2 max-w-[72px] text-center text-[10px] font-semibold uppercase leading-tight tracking-wide ${
                current ? "text-primary" : done ? "text-foreground" : "text-muted-foreground/60"
              }`}
            >
              {s.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function ActiveStepCard({
  step,
  index,
  total,
  submitting,
  onComplete,
}: {
  step: WorkflowStepState
  index: number
  total: number
  submitting: boolean
  onComplete: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
    >
      <div className="rounded-2xl border border-primary/30 bg-card p-6 shadow-card ring-1 ring-primary/10">
        <div className="t-eyebrow text-primary">
          Step {index + 1} of {total}
        </div>
        <h2 className="mt-2 text-2xl font-black leading-tight tracking-tight text-foreground sm:text-3xl">{step.label}</h2>
        <p className="mt-2 text-base leading-relaxed text-muted-foreground">{step.description}</p>

        <Button
          size="lg"
          onClick={onComplete}
          disabled={submitting}
          className="mt-6 hidden h-12 w-full text-base font-semibold sm:flex"
        >
          {submitting ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : null}
          Complete step
          {!submitting && <ArrowRight className="ml-2 h-5 w-5" />}
        </Button>
      </div>

      {/* Mobile: fixed, always-reachable primary action */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 p-4 backdrop-blur sm:hidden">
        <Button
          size="lg"
          onClick={onComplete}
          disabled={submitting}
          className="h-12 w-full text-base font-semibold"
        >
          {submitting ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : null}
          Complete step
          {!submitting && <ArrowRight className="ml-2 h-5 w-5" />}
        </Button>
      </div>
    </motion.div>
  )
}

function CompletionScreen({
  job,
  meta,
  streamLabel,
}: {
  job: CollectionJob
  meta: RouteMeta
  streamLabel: string
}) {
  const count = job.event_count
  // After a job COMPLETES the backend drops this bin's pending count (and with
  // it the simulated capacity). Those numbers are READ BACK from /operations —
  // never assumed, never computed here.
  const [bin, setBin] = useState<BinOperation | null>(null)
  useEffect(() => {
    let mounted = true
    api
      .operations()
      .then((res) => {
        if (!mounted) return
        setBin(res.operations.bins.find((b) => b.bin_id === job.bin_id) ?? null)
      })
      .catch(() => {})
    return () => { mounted = false }
  }, [job.bin_id])

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="rounded-2xl border border-success/30 bg-success/5 p-8 text-center"
    >
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}
        className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success text-white"
      >
        <Check className="h-8 w-8" aria-hidden />
      </motion.div>
      <h2 className="mt-5 text-3xl font-black leading-tight tracking-tight text-foreground">
        Collection complete
      </h2>
      <p className="mt-2 flex items-center justify-center gap-2 text-sm font-semibold text-foreground">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: meta.hex }} aria-hidden />
        {meta.label} · {streamLabel}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        {count} item{count === 1 ? "" : "s"} processed. Compliance results for each audit event are unchanged.
      </p>

      {/* The emptied bin, straight from /operations. */}
      {bin && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.3 }}
          className="mx-auto mt-6 max-w-sm rounded-xl border border-border bg-card p-4 text-left"
        >
          <div className="t-eyebrow">{bin.label} bin now</div>
          <div className="mt-2 flex items-end justify-between gap-4">
            <div>
              <div className="text-3xl font-black tabular-nums text-foreground">
                {bin.pending_collection_count}
              </div>
              <div className="t-meta">item{bin.pending_collection_count === 1 ? "" : "s"} pending collection</div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-black tabular-nums text-foreground">{bin.fill_percent}%</div>
              <div className="t-meta">simulated capacity</div>
            </div>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
            {bin.fill_percent > 0 && (
              <div
                className="h-full rounded-full bg-success transition-all duration-700"
                style={{ width: `${Math.min(Math.max(bin.fill_percent, 0), 100)}%` }}
              />
            )}
          </div>
          <p className="mt-3 t-meta">{bin.collection_state_label}</p>
          <p className="mt-1 t-meta">
            {bin.routed_event_count} audit record{bin.routed_event_count === 1 ? "" : "s"} for this
            stream are retained permanently.
          </p>
        </motion.div>
      )}

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Button asChild variant="outline">
          <Link href={`/disposal/job/${job.job_id}`}>
            <ClipboardList className="mr-2 h-4 w-4" />
            View collection record
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="#included-events">
            <FileText className="mr-2 h-4 w-4" />
            View audit events
          </Link>
        </Button>
        <Button asChild>
          <Link href="/scan">
            <ScanLine className="mr-2 h-4 w-4" />
            Analyze another item
          </Link>
        </Button>
      </div>

      <Button asChild variant="ghost" size="sm" className="mt-4 text-muted-foreground">
        <Link href="/operations">
          <ArrowLeft className="mr-2 h-3.5 w-3.5" />
          Back to operations
        </Link>
      </Button>
    </motion.div>
  )
}
