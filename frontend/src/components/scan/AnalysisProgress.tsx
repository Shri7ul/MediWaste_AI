"use client"
import { useEffect, useState } from "react"
import { Check, Loader2 } from "lucide-react"
import { motion } from "framer-motion"

/**
 * The four-stage pipeline the operator watches while `/analyze` is in flight.
 *
 * Honesty rules that this component must keep:
 *  - No percentage is shown. The backend does not report progress, so any number
 *    here would be invented.
 *  - No internal service, vendor or framework name is exposed. The stages are
 *    named after the WORK, not the implementation.
 *  - The final stage never auto-completes. It stays in-flight until the real
 *    response arrives and the parent replaces this view, so the UI cannot claim
 *    a decision that has not been made.
 */
const STAGES = [
  { id: "identify", label: "Identify", detail: "Recognising the item in the image" },
  { id: "policy", label: "Policy", detail: "Matching it to a segregation rule" },
  { id: "evidence", label: "Evidence", detail: "Retrieving supporting guidance" },
  { id: "decision", label: "Decision", detail: "Preparing the recommended bin" },
] as const

export function AnalysisProgress() {
  // Indicative pacing only — the last stage is intentionally never marked done.
  const [reached, setReached] = useState(0)

  useEffect(() => {
    const timers = [
      setTimeout(() => setReached(1), 900),
      setTimeout(() => setReached(2), 2200),
      setTimeout(() => setReached(3), 3800),
    ]
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
      <div className="t-eyebrow">Analysing</div>
      <h2 className="t-display mt-1">Working out where this belongs</h2>

      <ol className="mt-6 space-y-1">
        {STAGES.map((s, i) => {
          const done = i < reached
          const current = i === reached
          const state = done ? "Done" : current ? "In progress" : "Waiting"
          return (
            <li
              key={s.id}
              aria-label={`${s.label}: ${state}`}
              className="flex items-start gap-3.5"
            >
              {/* Marker column with the connecting rail */}
              <div className="flex flex-col items-center self-stretch">
                <span
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                    done
                      ? "border-success bg-success text-white"
                      : current
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-card text-muted-foreground/40"
                  }`}
                  aria-hidden
                >
                  {done ? (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 320, damping: 18 }}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </motion.span>
                  ) : current ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  )}
                </span>
                {i < STAGES.length - 1 && (
                  <span
                    aria-hidden
                    className={`w-0.5 flex-1 ${done ? "bg-success/40" : "bg-border"}`}
                  />
                )}
              </div>

              <div className="pb-5">
                <div
                  className={`text-sm font-bold uppercase tracking-[0.14em] ${
                    current
                      ? "text-primary"
                      : done
                        ? "text-foreground"
                        : "text-muted-foreground/50"
                  }`}
                >
                  {s.label}
                </div>
                <div
                  className={`mt-0.5 text-sm ${
                    current || done ? "text-muted-foreground" : "text-muted-foreground/50"
                  }`}
                >
                  {s.detail}
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      <p className="t-meta mt-1">
        The bin is chosen by the deterministic policy engine, not by the language
        model.
      </p>
    </div>
  )
}
