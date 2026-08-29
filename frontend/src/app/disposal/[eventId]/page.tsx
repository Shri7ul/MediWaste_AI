"use client"
import { useCallback, useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api/client"
import { WorkflowDefinition, DisposalWorkflow, WorkflowStepState, RouteMeta } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { WasteBin } from "@/components/ui/waste-bin"
import { Button } from "@/components/ui/button"
import { Check, ArrowRight, ArrowLeft, Loader2, AlertTriangle, ScanLine, FileText, Boxes } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"

interface EventLite {
  waste_type: string | null
  expected_route: string | null
  collection_job_id: string | null
}

// Compact context for the collection job this audit event belongs to (if any).
// Sourced entirely from the real job API — never fabricated. Used only to point
// the operator at the authoritative collection-job workflow; opening this page
// never creates a job.
interface JobContext {
  job_id: string
  event_count: number
  route_label: string
  is_complete: boolean
}

export default function DisposalWorkflowPage({ params }: { params: { eventId: string } }) {
  const [definition, setDefinition] = useState<WorkflowDefinition | null>(null)
  const [workflow, setWorkflow] = useState<DisposalWorkflow | null>(null)
  const [routeMeta, setRouteMeta] = useState<Record<string, RouteMeta> | undefined>(undefined)
  const [event, setEvent] = useState<EventLite | null>(null)
  const [jobContext, setJobContext] = useState<JobContext | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [def, wf] = await Promise.all([
        api.disposalDefinition(),
        api.disposalWorkflow(params.eventId),
      ])
      setDefinition(def)
      setWorkflow(wf.workflow)
      // Non-fatal enrichers for the hero (waste type + route colour) and, if the
      // event was collected as part of a collection job, a read-only pointer to
      // that job's authoritative workflow. Opening this page NEVER starts a job.
      api.eventDetail(params.eventId)
        .then((r) => {
          const jobId = r.event?.collection_job_id ?? null
          setEvent({
            waste_type: r.event?.canonical_category ?? null,
            expected_route: r.event?.expected_route ?? null,
            collection_job_id: jobId,
          })
          if (jobId) {
            // Read-only fetch of the existing job — no mutation, no creation.
            api.collectionJob(jobId)
              .then((jr) => setJobContext({
                job_id: jr.job.job_id,
                event_count: jr.job.event_count,
                route_label: jr.job.route_meta?.label || jr.job.route_code,
                is_complete: jr.job.workflow?.is_complete ?? jr.job.status === "COMPLETED",
              }))
              .catch(() => {})
          }
        })
        .catch(() => {})
      api.policy().then((p) => setRouteMeta(p.route_meta)).catch(() => {})
    } catch (e: any) {
      setLoadError(e instanceof ApiError && e.status === 404
        ? "This disposal record could not be found."
        : e.message || "Failed to load the disposal workflow.")
    }
  }, [params.eventId])

  useEffect(() => { load() }, [load])

  const handleComplete = async (stepId: string) => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.completeDisposalStep(params.eventId, stepId)
      if (res?.workflow) setWorkflow(res.workflow)
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

  if (!definition || !workflow) {
    return (
      <div className="mx-auto max-w-2xl animate-pulse space-y-6 py-6">
        <div className="h-28 rounded-2xl bg-muted" />
        <div className="h-16 rounded-xl bg-muted" />
        <div className="h-52 rounded-2xl bg-muted" />
      </div>
    )
  }

  const meta = resolveStream(event?.expected_route, routeMeta)
  const wasteLabel = event?.waste_type || "Medical waste"
  const activeStep = workflow.steps.find((s) => s.id === workflow.current_step) || null

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-28 sm:pb-8">
      {/* Hero */}
      <div className="flex items-center gap-5 rounded-2xl border border-border bg-card p-5 shadow-soft">
        <WasteBin hex={event?.expected_route ? meta.hex : "#94a3b8"} label={meta.label} size="md" />
        <div className="min-w-0">
          <div className="t-eyebrow">Disposal workflow</div>
          <h1 className="mt-1 t-display">
            {wasteLabel}
          </h1>
          <p className="text-sm text-muted-foreground">
            {event?.expected_route ? `${meta.label} bin · ${meta.category}` : "Route pending"}
          </p>
          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground/70">
            Event {params.eventId}
          </p>
        </div>
      </div>

      {jobContext && (
        <div className="flex flex-col gap-3 rounded-2xl border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <Boxes className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                Part of a {jobContext.route_label} collection
                {jobContext.is_complete ? " (completed)" : ""}
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                This item was collected together with{" "}
                {jobContext.event_count} item{jobContext.event_count === 1 ? "" : "s"} in one
                collection cycle. Disposal is tracked at the collection-job level.
              </p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm" className="shrink-0 font-semibold">
            <Link href={`/disposal/job/${jobContext.job_id}`}>
              {jobContext.is_complete ? "View collection" : "Continue disposal"}
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      )}

      <ProgressRail steps={workflow.steps} currentId={workflow.current_step} />

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <span>{error}</span>
        </div>
      )}

      <AnimatePresence mode="wait">
        {workflow.is_complete ? (
          <CompletionScreen key="done" wasteLabel={wasteLabel} meta={meta} hasRoute={!!event?.expected_route} eventId={params.eventId} />
        ) : activeStep ? (
          <ActiveStepCard
            key={activeStep.id}
            step={activeStep}
            index={workflow.completed_count}
            total={workflow.total_steps}
            submitting={submitting}
            onComplete={() => handleComplete(activeStep.id)}
          />
        ) : null}
      </AnimatePresence>
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
  wasteLabel,
  meta,
  hasRoute,
  eventId,
}: {
  wasteLabel: string
  meta: RouteMeta
  hasRoute: boolean
  eventId: string
}) {
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
        <Check className="h-8 w-8" />
      </motion.div>
      <h2 className="mt-5 text-3xl font-black leading-tight tracking-tight text-foreground">
        Disposal complete
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        All required disposal steps have been recorded to the audit trail.
      </p>

      <div className="mx-auto mt-6 flex max-w-xs items-center justify-center gap-8">
        <div className="text-center">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Waste</div>
          <div className="mt-1 font-semibold text-foreground">{wasteLabel}</div>
        </div>
        <div className="text-center">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Route</div>
          <div className="mt-1 flex items-center justify-center gap-2 font-semibold text-foreground">
            {hasRoute && <span className="h-3 w-3 rounded-full" style={{ backgroundColor: meta.hex }} />}
            {hasRoute ? `${meta.label}` : "—"}
          </div>
        </div>
      </div>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Button asChild variant="outline">
          <Link href={`/events?event=${eventId}`}>
            <FileText className="mr-2 h-4 w-4" />
            View audit record
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

