"use client"
import { motion } from "framer-motion"
import Link from "next/link"
import { CheckCircle2, AlertTriangle, ArrowRight, FileSearch } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
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

export function ComplianceResult({
  verifyData,
  analyzeData,
  actualRoute,
  onViewEvidence,
  onContinue,
}: ComplianceResultProps) {
  const isCorrect = verifyData.verification.status === "CORRECT"
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
      <Card className="overflow-hidden shadow-card border-border/70">
        <div
          className={`px-6 py-4 flex items-center gap-3 text-white ${
            isCorrect ? "bg-success" : "bg-destructive"
          }`}
        >
          {isCorrect ? (
            <CheckCircle2 className="h-6 w-6 shrink-0" />
          ) : (
            <AlertTriangle className="h-6 w-6 shrink-0" />
          )}
          <div>
            <h2 className="text-lg font-bold tracking-tight">
              {isCorrect ? "Correct disposal" : "Wrong waste stream"}
            </h2>
            <p className="text-sm text-white/90">
              {isCorrect
                ? "The item was placed in the recommended bin."
                : "The item should be moved to the recommended bin."}
            </p>
          </div>
        </div>

        <CardContent className="pt-8">
          <div className="flex items-center justify-center gap-6 sm:gap-12">
            <BinColumn caption="Recommended" meta={expectedMeta} />
            <ArrowRight className="h-7 w-7 text-muted-foreground/40 shrink-0" />
            <BinColumn
              caption="You chose"
              meta={actualMeta}
              tone={isCorrect ? "ok" : "bad"}
            />
          </div>

          {!isCorrect && verifyData.verification.reason_code && (
            <div className="mt-6 rounded-lg bg-destructive/10 text-destructive text-center py-2.5 px-4 text-sm font-medium">
              {humanReason(verifyData.verification.reason_code)}
            </div>
          )}

          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            {isCorrect ? (
              <>
                <Button asChild>
                  <Link href={`/disposal/${eventId}`}>Start disposal</Link>
                </Button>
                <Button variant="outline" onClick={onViewEvidence}>
                  <FileSearch className="mr-2 h-4 w-4" /> Why this route?
                </Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={onViewEvidence}>
                  <FileSearch className="mr-2 h-4 w-4" /> Why this route?
                </Button>
                <Button asChild>
                  <Link href={`/disposal/${eventId}`}>Start disposal</Link>
                </Button>
              </>
            )}
            <Button variant="ghost" onClick={onContinue}>
              Scan another item
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="text-center text-xs text-muted-foreground">
        Audit record <span className="font-mono">{eventId}</span>
      </div>
    </motion.div>
  )
}

function BinColumn({
  caption,
  meta,
  tone,
}: {
  caption: string
  meta: { hex: string; label: string }
  tone?: "ok" | "bad"
}) {
  return (
    <div className="text-center space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {caption}
      </div>
      <WasteBin hex={meta.hex} label={meta.label} size="md" className="mx-auto" />
      <div
        className={`font-bold ${
          tone === "bad" ? "text-destructive" : "text-foreground"
        }`}
      >
        {meta.label}
      </div>
    </div>
  )
}

function humanReason(code: string): string {
  const map: Record<string, string> = {
    WRONG_ROUTE: "This bin does not match the recommended waste stream.",
    HAZARD_MISMATCH: "Hazardous waste was placed in a non-hazardous bin.",
  }
  return map[code] || `Segregation issue: ${code.replace(/_/g, " ").toLowerCase()}.`
}
