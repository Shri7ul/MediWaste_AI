"use client"

import { usePathname } from "next/navigation"
import { Check } from "lucide-react"
import { STAGES, stageForPath, stageIndex } from "@/lib/narrative"
import { useStageOverride } from "./StageContext"

/**
 * A single, quiet strip under the header showing where the current screen sits
 * in SCAN → DECIDE → VERIFY → ACT → COLLECT → PROVE.
 *
 * Deliberately low-contrast: it orients, it does not compete with the screen's
 * own hero. Completed stages carry a check as well as a colour so the state is
 * never conveyed by colour alone.
 */
export function NarrativeRail() {
  const pathname = usePathname()
  const override = useStageOverride()
  const active = override ?? stageForPath(pathname)
  const activeIdx = stageIndex(active)

  if (activeIdx < 0) return null

  return (
    <div className="border-b border-border/70 bg-card/60">
      <nav
        aria-label="Workflow progress"
        className="container flex items-center gap-1 overflow-x-auto py-2 sm:gap-2"
      >
        {STAGES.map((s, i) => {
          const done = i < activeIdx
          const current = i === activeIdx
          return (
            <div key={s.id} className="flex shrink-0 items-center gap-1 sm:gap-2">
              <span
                aria-current={current ? "step" : undefined}
                title={s.hint}
                className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] transition-colors sm:text-[11px] ${
                  current
                    ? "bg-primary/10 text-primary"
                    : done
                      ? "text-foreground/70"
                      : "text-muted-foreground/50"
                }`}
              >
                {done ? (
                  <Check className="h-3 w-3" aria-hidden />
                ) : (
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      current ? "bg-primary" : "bg-muted-foreground/30"
                    }`}
                    aria-hidden
                  />
                )}
                {s.label}
              </span>
              {i < STAGES.length - 1 && (
                <span
                  aria-hidden
                  className={`h-px w-3 sm:w-6 ${done ? "bg-foreground/25" : "bg-border"}`}
                />
              )}
            </div>
          )
        })}
      </nav>
    </div>
  )
}
