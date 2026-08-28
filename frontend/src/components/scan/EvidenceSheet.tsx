"use client"
import { useState } from "react"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AnalyzeResponse, VerifyResponse, EvidenceRecord } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { Sparkles, BookOpen, ShieldCheck, ListChecks, AlertCircle } from "lucide-react"

interface EvidenceSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  analyzeData: AnalyzeResponse | null;
  verifyData?: VerifyResponse | null;
}

const TOP_N = 3

function EvidenceCard({ ev }: { ev: EvidenceRecord }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="truncate font-mono text-xs text-muted-foreground">
          {ev.source || "Source unavailable"}
          {ev.page != null && ev.page !== "" ? ` · p.${ev.page}` : ""}
          {ev.section ? ` · ${ev.section}` : ""}
        </span>
        {typeof ev.score === "number" && (
          <span className="rounded bg-secondary px-2 py-0.5 text-[11px] tabular-nums text-secondary-foreground">
            {ev.score.toFixed(2)}
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed text-foreground/90">{ev.text}</p>
      {ev.evidence_id && (
        <div className="mt-2 font-mono text-[10px] text-muted-foreground/70">{ev.evidence_id}</div>
      )}
    </div>
  )
}

export function EvidenceSheet({ open, onOpenChange, analyzeData, verifyData }: EvidenceSheetProps) {
  const [showAll, setShowAll] = useState(false)
  if (!analyzeData) return null

  const decision = analyzeData.analysis.decision
  const meta = resolveStream(decision.expected_route, analyzeData.analysis.route_meta)

  // Prefer the post-verify payload (it re-queries RAG with the actual_route).
  const rag = verifyData?.rag || analyzeData.rag
  const explanation = verifyData?.explanation || analyzeData.explanation

  const evidence: EvidenceRecord[] = rag?.evidence ?? []
  const evidenceCount = evidence.length
  // Emptiness is driven ONLY by how many passages were retrieved — never by
  // guidance.length, explanation === null, or evidence_ids_used.
  const hasEvidence = evidenceCount > 0
  const shown = showAll ? evidence : evidence.slice(0, TOP_N)

  // Backend status is "OK" (NOT "SUCCESS"). SKIPPED_NO_EVIDENCE = grounding
  // gate withheld the narrative; UNAVAILABLE = model/key down.
  const hasExplanation = explanation?.status === "OK" && !!explanation?.explanation
  const whyRoute = explanation?.why_route
  const guidance: string[] = explanation?.guidance ?? []

  const evidenceCountLabel =
    evidenceCount === 0
      ? "No supporting evidence was retrieved."
      : `${evidenceCount} retrieved ${evidenceCount === 1 ? "passage" : "passages"}`

  const explanationNote =
    explanation?.status === "SKIPPED_NO_EVIDENCE"
      ? "The AI narrative was withheld because no citable evidence was retrieved. The bin below is still set by the deterministic policy engine."
      : explanation?.status === "UNAVAILABLE"
      ? "The AI explanation service is currently unavailable. The bin below is still set by the deterministic policy engine."
      : "An evidence-grounded explanation isn't available for this item. The bin shown is still determined by the deterministic policy engine."

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-[560px] flex flex-col">
        <SheetHeader>
          <SheetTitle className="text-xl">Why this route?</SheetTitle>
          <SheetDescription className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: meta.hex }} />
            {decision.waste_type} → {meta.label} bin
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 mt-4 pr-4">
          <div className="space-y-6">
            {/* 1 — Plain-English summary from the policy engine (always present) */}
            <div className="rounded-lg bg-accent/60 p-4 text-sm leading-relaxed text-foreground">
              {whyRoute ||
                `Hospital segregation policy routes ${decision.waste_type?.toLowerCase()} waste to the ${meta.label} (${meta.category}) bin.`}
            </div>

            {/* 2 — Policy rule (the deciding authority) */}
            <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm">
              <ShieldCheck className="h-4 w-4 shrink-0 text-primary" />
              <span className="text-muted-foreground">
                Policy <span className="font-medium text-foreground">{decision.rule_id}</span> · v{decision.policy_version}
              </span>
            </div>

            {/* 3 — Retrieved evidence (RAG supports) */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <BookOpen className="h-4 w-4" />
                  <h3 className="text-sm font-semibold">Evidence</h3>
                </div>
                <span className="text-xs font-medium text-muted-foreground">{evidenceCountLabel}</span>
              </div>

              {hasEvidence ? (
                <>
                  <div className="space-y-3">
                    {shown.map((ev, idx) => (
                      <EvidenceCard key={ev.evidence_id ?? idx} ev={ev} />
                    ))}
                  </div>
                  {evidenceCount > TOP_N && (
                    <button
                      type="button"
                      onClick={() => setShowAll((v) => !v)}
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      {showAll ? "Show fewer" : `View all evidence (${evidenceCount})`}
                    </button>
                  )}
                </>
              ) : (
                <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {rag?.status === "UNAVAILABLE"
                      ? "The evidence retrieval service is currently unavailable."
                      : "No supporting evidence was retrieved for this item."}
                  </span>
                </div>
              )}
            </section>

            {/* 4 — AI explanation (LLM explains, grounded in evidence) */}
            <section className="space-y-2">
              <div className="flex items-center gap-2 text-primary">
                <Sparkles className="h-4 w-4" />
                <h3 className="text-sm font-semibold">
                  Explanation{explanation?.model ? ` (${explanation.model})` : ""}
                </h3>
              </div>
              {hasExplanation ? (
                <div className="rounded-lg border border-border bg-card p-4 text-sm leading-relaxed text-foreground">
                  {explanation.explanation}
                  {explanation.evidence_ids_used?.length > 0 && (
                    <div className="mt-3 text-[11px] font-medium uppercase tracking-wide text-primary/70">
                      Grounded in {explanation.evidence_ids_used.length} cited{" "}
                      {explanation.evidence_ids_used.length === 1 ? "passage" : "passages"}
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
                  {explanationNote}
                </div>
              )}
            </section>

            {/* 5 — Handling guidance (from the grounded explanation) */}
            {guidance.length > 0 && (
              <section className="space-y-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <ListChecks className="h-4 w-4" />
                  <h3 className="text-sm font-semibold">Handling guidance</h3>
                </div>
                <ul className="space-y-2">
                  {guidance.map((g, idx) => (
                    <li key={idx} className="flex gap-2 rounded-lg border border-border bg-card p-3 text-xs leading-relaxed text-foreground/90">
                      <span className="text-primary">•</span>
                      <span>{g}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
