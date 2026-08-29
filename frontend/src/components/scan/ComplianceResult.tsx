"use client"
import { motion } from "framer-motion"
import Link from "next/link"
import { CheckCircle2, AlertTriangle, AlertCircle, ArrowRight, FileSearch, ScanLine } from "lucide-react"
import { Button } from "@/components/ui/button"
import { VerifyResponse, AnalyzeResponse } from "@/lib/types/api"
import { WasteBin } from "@/components/ui/waste-bin"
import { resolveStream } from "@/lib/waste"

interface ComplianceResultProps {
  verifyData: VerifyResponse;
  analyzeData: AnalyzeResponse;
  actualRoute: string;
  onViewEvidence: () => void;
  onContinue: () => void;
}

/**
 * The compliance verdict, rendered as the hero of the screen.
 *
 * The status string comes straight from `POST /verify` — this component maps it
 * to words and colour and does not evaluate compliance itself. REVIEW_REQUIRED is
 * rendered as its own amber state rather than being folded into VIOLATION.
 */
const VERDICT = {
  CORRECT: {
    band: "bg-success",
    headline: "Correct disposal",
    sub: "The item was placed in the recommended bin.",
    Icon: CheckCircle2,
  },
  VIOLATION: {
    band: "bg-destructive",
    headline: "Wrong waste stream",
    sub: "Move the item to the recommended bin.",
    Icon: AlertTriangle,
  },
  REVIEW_REQUIRED: {
    band: "bg-warning",
    headline: "Review required",
    sub: "This disposal needs a supervisor check.",
    Icon: AlertCircle,
  },
  PENDING: {
    band: "bg-muted-foreground",
    headline: "Awaiting verification",
    sub: "No compliance outcome has been recorded yet.",
    Icon: AlertCircle,
  },
} as const

export function ComplianceResult({
  verifyData,
  analyzeData,
  actualRoute,
  onViewEvidence,
  onContinue,
}: ComplianceResultProps) {
  const status = verifyData.verification.status
  const v = VERDICT[status] ?? VERDICT.PENDING
  const isCorrect = status === "CORRECT"
  const isMismatch = status === "VIOLATION"
  const expectedRoute = analyzeData.analysis.decision.expected_route
  const expectedMeta = resolveStream(expectedRoute, analyzeData.analysis.route_meta)
  const actualMeta = resolveStream(actualRoute, analyzeData.analysis.route_meta)
  const eventId = verifyData.event_id

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="space-y-5"
    >
      <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-card">
        {/* VERDICT — the single dominant element on this screen. */}
        <div role="status" aria-live="polite" className={`px-6 py-7 text-white ${v.band} sm:px-8`}>
          <div className="flex items-start gap-4">
            <motion.span
              initial={{ scale: 0.4, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 18 }}
              className="mt-1 shrink-0"
              aria-hidden
            >
              <v.Icon className="h-9 w-9" />
            </motion.span>
            <div className="min-w-0">
              <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/75">
                Compliance
              </div>
              <h2 className="mt-1 text-3xl font-black leading-[1.05] tracking-tight sm:text-4xl">
                {v.headline}
              </h2>
              <p className="mt-2 text-sm font-medium text-white/90">{v.sub}</p>
            </div>
          </div>
        </div>

        <div className="p-6 sm:p-8">
          {/* EXPECTED vs ACTUAL */}
          <div className="flex items-start justify-center gap-6 sm:gap-12">
            <BinColumn caption="Recommended" meta={expectedMeta} />
            <ArrowRight className="mt-10 h-7 w-7 shrink-0 text-muted-foreground/40" aria-hidden />
            <BinColumn caption="You used" meta={actualMeta} mismatch={isMismatch} />
          </div>

          {!isCorrect && verifyData.verification.reason_code && (
            <div
              className={`mx-auto mt-6 max-w-md rounded-lg px-4 py-2.5 text-center text-sm font-medium ${
                isMismatch
                  ? "bg-destructive/10 text-destructive"
                  : "bg-warning/10 text-warning"
              }`}
            >
              {humanReason(verifyData.verification.reason_code)}
            </div>
          )}

          {/* Action order follows the outcome. On a correct disposal the next real
              step is the disposal workflow. On a mismatch the operator needs the
              reasoning first, so "Why this route?" becomes the primary action and
              the corrective disposal workflow sits beside it. Buttons are
              full-width and 48px tall on a phone. */}
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            {isMismatch ? (
              <>
                <Button size="lg" onClick={onViewEvidence} className="h-12 w-full font-semibold sm:w-auto">
                  <FileSearch className="mr-2 h-4 w-4" aria-hidden /> Why this route?
                </Button>
                <Button asChild variant="outline" size="lg" className="h-12 w-full sm:w-auto">
                  <Link href={`/disposal/${eventId}`}>
                    Start disposal
                    <ArrowRight className="ml-2 h-4 w-4" aria-hidden />
                  </Link>
                </Button>
              </>
            ) : (
              <>
                <Button asChild size="lg" className="h-12 w-full font-semibold sm:w-auto">
                  <Link href={`/disposal/${eventId}`}>
                    Start disposal
                    <ArrowRight className="ml-2 h-4 w-4" aria-hidden />
                  </Link>
                </Button>
                <Button variant="outline" size="lg" onClick={onViewEvidence} className="h-12 w-full sm:w-auto">
                  <FileSearch className="mr-2 h-4 w-4" aria-hidden /> Why this route?
                </Button>
              </>
            )}
            <Button variant="ghost" size="lg" onClick={onContinue} className="h-12 w-full sm:w-auto">
              <ScanLine className="mr-2 h-4 w-4" aria-hidden /> Scan another item
            </Button>
          </div>
        </div>
      </div>

      <p className="text-center t-meta">
        Recorded as audit event <span className="font-mono">{eventId}</span>
      </p>
    </motion.div>
  )
}

function BinColumn({
  caption,
  meta,
  mismatch,
}: {
  caption: string
  meta: { hex: string; label: string }
  mismatch?: boolean
}) {
  return (
    <div className="min-w-0 max-w-[130px] space-y-2 text-center">
      <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
        {caption}
      </div>
      <WasteBin hex={meta.hex} label={meta.label} size="md" className="mx-auto" />
      <div className={`break-words font-bold ${mismatch ? "text-destructive" : "text-foreground"}`}>
        {meta.label}
        {/* Mismatch is stated in words too, never by colour alone. */}
        {mismatch && (
          <span className="mt-0.5 block text-[10px] font-bold uppercase tracking-wide">
            Mismatch
          </span>
        )}
      </div>
    </div>
  )
}

function humanReason(code: string): string {
  const map: Record<string, string> = {
    WRONG_ROUTE: "This bin does not match the recommended waste stream.",
    WRONG_WASTE_STREAM: "This bin does not match the recommended waste stream.",
    HAZARD_MISMATCH: "Hazardous waste was placed in a non-hazardous bin.",
  }
  return map[code] || `Segregation issue: ${code.replace(/_/g, " ").toLowerCase()}.`
}
