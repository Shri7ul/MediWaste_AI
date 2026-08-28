"use client"
import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api/client"
import { EventRecord, AnalyzeResponse, ComplianceStatus } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { EvidenceSheet } from "@/components/scan/EvidenceSheet"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  CheckCircle2, AlertTriangle, AlertCircle, Clock, ChevronRight, RefreshCw,
  ScanLine, FileSearch, ShieldCheck, BookOpen, ArrowRight,
} from "lucide-react"
import { motion } from "framer-motion"
import Link from "next/link"

type FilterKey = "ALL" | "CORRECT" | "VIOLATION" | "REVIEW_REQUIRED" | "PENDING_VERIFICATION"

const STATUS_META: Record<ComplianceStatus, { label: string; text: string; bg: string; border: string; icon: React.ReactNode }> = {
  CORRECT: { label: "Correct disposal", text: "text-success", bg: "bg-success/10", border: "border-success/30", icon: <CheckCircle2 className="h-4 w-4" /> },
  VIOLATION: { label: "Wrong waste stream", text: "text-destructive", bg: "bg-destructive/10", border: "border-destructive/30", icon: <AlertTriangle className="h-4 w-4" /> },
  REVIEW_REQUIRED: { label: "Review required", text: "text-warning", bg: "bg-warning/10", border: "border-warning/40", icon: <AlertCircle className="h-4 w-4" /> },
  PENDING_VERIFICATION: { label: "Awaiting verification", text: "text-muted-foreground", bg: "bg-muted", border: "border-border", icon: <Clock className="h-4 w-4" /> },
}

function statusMeta(s: string | null | undefined) {
  return STATUS_META[(s as ComplianceStatus)] ?? STATUS_META.PENDING_VERIFICATION
}

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "CORRECT", label: "Correct" },
  { key: "VIOLATION", label: "Violations" },
  { key: "REVIEW_REQUIRED", label: "Review" },
  { key: "PENDING_VERIFICATION", label: "Pending" },
]

export default function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<FilterKey>("ALL")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<EventRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.events(100, 0)
      setEvents(res.events)
    } catch (e: any) {
      setError(e?.message || "Could not load audit events.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Deep-link support: /events?event=<id> opens that event's detail directly
  // (used by the disposal completion "View audit record" action).
  useEffect(() => {
    if (typeof window === "undefined") return
    const id = new URLSearchParams(window.location.search).get("event")
    if (id) setSelectedId(id)
  }, [])

  useEffect(() => {
    if (!selectedId) { setDetail(null); return }
    let active = true
    setDetailLoading(true)
    api.eventDetail(selectedId)
      .then((r) => { if (active) setDetail(r.event) })
      .catch(() => { if (active) setDetail(null) })
      .finally(() => { if (active) setDetailLoading(false) })
    return () => { active = false }
  }, [selectedId])

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: events.length }
    for (const e of events) {
      const k = e.compliance_status || "PENDING_VERIFICATION"
      c[k] = (c[k] || 0) + 1
    }
    return c
  }, [events])

  const filtered = useMemo(
    () => (filter === "ALL" ? events : events.filter((e) => (e.compliance_status || "PENDING_VERIFICATION") === filter)),
    [events, filter]
  )

  const synthesized: AnalyzeResponse | null = useMemo(() => {
    if (!detail) return null
    const p = detail.payload || {}
    return {
      status: "ok",
      event_id: detail.event_id,
      image_url: "",
      analysis: {
        detections: p.detections ?? [],
        primary: (p.primary as any) ?? { item: detail.canonical_category ?? "", confidence: detail.confidence ?? 0 },
        decision: {
          waste_type: detail.canonical_category ?? "",
          expected_route: detail.expected_route ?? "",
          rule_id: detail.rule_id ?? "",
          policy_version: detail.policy_version ?? "",
        },
        context: p.context ?? null,
        mixed_waste: p.mixed_waste ?? false,
        verification: { status: (detail.compliance_status as any) ?? "PENDING", reason_code: detail.reason_code ?? undefined },
        model: { id: detail.model_id ?? "", version: detail.model_version ?? "", ref: "" },
        valid_routes: [],
        route_meta: {},
      },
      rag: p.rag ?? { status: "UNAVAILABLE", evidence: [], evidence_ids: [] },
      explanation: p.explanation ?? { status: "UNAVAILABLE", explanation: null, why_route: null, guidance: [], evidence_ids_used: [], limitations: null },
      audit_event: null,
      timings: null,
    }
  }, [detail])

  // RENDER
  if (error) {
    return (
      <div className="mx-auto mt-10 max-w-md rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
        <AlertTriangle className="mx-auto h-9 w-9 text-destructive" />
        <h2 className="mt-3 text-lg font-semibold text-foreground">Audit events unavailable</h2>
        <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        <Button onClick={load} variant="outline" className="mt-5">
          <RefreshCw className="mr-2 h-4 w-4" /> Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Audit Events</h1>
        <p className="mt-1 text-sm text-muted-foreground">Historical compliance events and routing decisions.</p>
      </div>

      {!loading && events.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => {
            const n = counts[f.key] ?? 0
            const active = filter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                  active ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                {f.label}
                <span className={`tabular-nums ${active ? "opacity-80" : "text-muted-foreground/60"}`}>{n}</span>
              </button>
            )
          })}
        </div>
      )}

      {loading ? (
        <div className="animate-pulse space-y-3">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-20 rounded-xl bg-muted" />)}
        </div>
      ) : events.length === 0 ? (
        <EmptyState />
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
          No events match this filter.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((ev, i) => (
            <EventRow key={ev.event_id} ev={ev} index={i} onSelect={() => setSelectedId(ev.event_id)} />
          ))}
        </div>
      )}

      <DetailSheet
        selectedId={selectedId}
        detail={detail}
        loading={detailLoading}
        onClose={() => setSelectedId(null)}
        onOpenEvidence={() => setEvidenceOpen(true)}
      />

      <EvidenceSheet open={evidenceOpen} onOpenChange={setEvidenceOpen} analyzeData={synthesized} />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="mx-auto mt-10 max-w-lg rounded-2xl border border-border bg-card p-12 text-center shadow-soft">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
        <FileSearch className="h-8 w-8 text-primary" />
      </div>
      <h2 className="mt-5 text-xl font-bold tracking-tight text-foreground">No audit events yet</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Each analyzed and verified waste item is recorded here as a traceable compliance event.
      </p>
      <Button asChild className="mt-6">
        <Link href="/scan"><ScanLine className="mr-2 h-4 w-4" /> Analyze waste</Link>
      </Button>
    </div>
  )
}

function RouteChip({ code }: { code: string | null | undefined }) {
  if (!code) return <span className="text-muted-foreground/60">—</span>
  const meta = resolveStream(code, undefined)
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full ring-1 ring-black/5" style={{ backgroundColor: meta.hex }} />
      <span className="font-medium text-foreground">{code}</span>
    </span>
  )
}

function EventRow({ ev, index, onSelect }: { ev: EventRecord; index: number; onSelect: () => void }) {
  const s = statusMeta(ev.compliance_status)
  const time = ev.created_at
    ? new Date(ev.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—"
  return (
    <motion.button
      type="button"
      onClick={onSelect}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index, 8) * 0.03 }}
      className="group flex w-full items-center gap-4 rounded-2xl border border-border bg-card p-4 text-left shadow-soft transition-shadow hover:shadow-lift"
    >
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${s.bg} ${s.text}`}>
        {s.icon}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-base font-semibold text-foreground">{ev.canonical_category || "Unknown item"}</span>
          <span className={`inline-flex items-center rounded-full ${s.bg} px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${s.text}`}>
            {s.label}
          </span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">Expected <RouteChip code={ev.expected_route} /></span>
          <span className="inline-flex items-center gap-1.5">Actual <RouteChip code={ev.actual_route} /></span>
          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" /> {time}</span>
          {ev.station && <span>· {ev.station}</span>}
          {ev.collection_job_id && (
            <span className="inline-flex items-center rounded-full bg-accent px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              Collected · {ev.collection_job_id}
            </span>
          )}
        </div>
      </div>

      <ChevronRight className="hidden h-5 w-5 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-muted-foreground sm:block" />
    </motion.button>
  )
}

function DetailRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className={`mt-1 text-sm text-foreground ${mono ? "break-all font-mono text-xs" : ""}`}>{value}</div>
    </div>
  )
}

function DetailSheet({
  selectedId, detail, loading, onClose, onOpenEvidence,
}: {
  selectedId: string | null
  detail: EventRecord | null
  loading: boolean
  onClose: () => void
  onOpenEvidence: () => void
}) {
  return (
    <Sheet open={!!selectedId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="flex w-full flex-col p-0 sm:max-w-[560px]">
        {loading || !detail ? (
          <div className="animate-pulse space-y-4 p-6">
            <div className="h-6 w-1/2 rounded bg-muted" />
            <div className="h-24 rounded-xl bg-muted" />
            <div className="h-40 rounded-xl bg-muted" />
          </div>
        ) : (
          <DetailBody detail={detail} onOpenEvidence={onOpenEvidence} />
        )}
      </SheetContent>
    </Sheet>
  )
}

function DetailBody({ detail, onOpenEvidence }: { detail: EventRecord; onOpenEvidence: () => void }) {
  const s = statusMeta(detail.compliance_status)
  const p = detail.payload || {}
  const explanation = p.explanation
  const rag = p.rag
  const evidenceIds = detail.evidence_ids ?? explanation?.evidence_ids_used ?? []
  const hasEvidence = (rag?.evidence?.length ?? 0) > 0
  const hasExplanation = explanation?.status === "OK" && !!explanation?.explanation
  const time = detail.created_at ? new Date(detail.created_at).toLocaleString() : "—"

  return (
    <>
      <div className="border-b border-border p-6">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-primary">Audit event detail</div>
        <div className="mt-2 flex items-center gap-3">
          <span className={`inline-flex items-center gap-1.5 rounded-full ${s.bg} px-2.5 py-1 text-xs font-semibold ${s.text}`}>
            {s.icon} {s.label}
          </span>
        </div>
        <div className="mt-1 font-mono text-[11px] text-muted-foreground/70">{detail.event_id}</div>
      </div>

      <ScrollArea className="flex-1 p-6">
        <div className="space-y-8">
          {/* WHAT HAPPENED */}
          <section>
            <h3 className="mb-3 border-b border-border pb-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">
              What happened?
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <DetailRow label="Time" value={time} />
              <DetailRow label="Station / Ward" value={`${detail.station || "—"} / ${detail.ward || "—"}`} />
              <DetailRow label="Detected category" value={<span className="font-semibold">{detail.canonical_category || "—"}</span>} />
              <DetailRow label="Confidence" value={detail.confidence != null ? `${Math.round(detail.confidence * 100)}%` : "—"} />
              <DetailRow label="Expected route" value={<RouteChip code={detail.expected_route} />} />
              <DetailRow label="Actual route" value={<RouteChip code={detail.actual_route} />} />
            </div>
            {detail.reason_code && (
              <div className={`mt-4 flex items-center justify-between rounded-lg border ${s.border} ${s.bg} px-4 py-2.5`}>
                <span className={`text-xs font-semibold uppercase tracking-wide ${s.text}`}>{s.label}</span>
                <span className="font-mono text-[11px] text-muted-foreground">{detail.reason_code}</span>
              </div>
            )}
          </section>

          {/* WHY */}
          <section>
            <h3 className="mb-3 border-b border-border pb-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Why?
            </h3>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm">
              <ShieldCheck className="h-4 w-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                Decided by policy <span className="font-medium text-foreground">{detail.rule_id || "—"}</span>
                {detail.policy_version ? <> · v{detail.policy_version}</> : null}
              </span>
            </div>

            {hasExplanation ? (
              <p className="mt-3 rounded-lg border border-border bg-card p-4 text-sm leading-relaxed text-foreground">
                {explanation?.explanation}
              </p>
            ) : (
              <p className="mt-3 rounded-lg border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
                {explanation?.status === "SKIPPED_NO_EVIDENCE"
                  ? "The AI narrative was withheld because no citable evidence was retrieved. The route above was still set by the deterministic policy engine."
                  : "No evidence-grounded explanation was recorded for this event. The route above was still set by the deterministic policy engine."}
              </p>
            )}

            <Button variant="outline" onClick={onOpenEvidence} className="mt-3 w-full justify-between">
              <span className="inline-flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                {hasEvidence ? `Evidence & explanation (${rag?.evidence?.length})` : "Evidence & explanation"}
              </span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </section>

          {/* AUDIT RECORD */}
          <section>
            <h3 className="mb-3 border-b border-border pb-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Audit record
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <DetailRow label="Model" value={detail.model_id || "—"} mono />
              <DetailRow label="Image ID" value={detail.image_id || "—"} mono />
              <DetailRow label="RAG status" value={detail.rag_status || rag?.status || "—"} />
              <DetailRow label="Explanation status" value={detail.llm_status || explanation?.status || "—"} />
            </div>
            <div className="mt-4">
              <DetailRow
                label={`Evidence IDs${evidenceIds.length ? ` (${evidenceIds.length})` : ""}`}
                value={evidenceIds.length ? evidenceIds.join(", ") : "None"}
                mono
              />
            </div>
          </section>
        </div>
      </ScrollArea>

      <div className="border-t border-border bg-muted/20 p-4">
        <Button variant="outline" asChild className="w-full">
          <Link href={`/disposal/${detail.event_id}`}>View disposal workflow</Link>
        </Button>
      </div>
    </>
  )
}
