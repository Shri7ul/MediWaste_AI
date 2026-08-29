"use client"
import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { AnalyzeResponse } from "@/lib/types/api"
import { WasteBin } from "@/components/ui/waste-bin"
import { resolveStream } from "@/lib/waste"
import { Check, Loader2, ArrowRight } from "lucide-react"

interface ActualRouteSelectorProps {
  data: AnalyzeResponse;
  onVerify: (route: string) => void;
  isVerifying: boolean;
}

/**
 * The primary verification interaction: the operator records the bin they
 * ACTUALLY used.
 *
 * The tiles are deliberately neutral — the recommended bin is not highlighted
 * here, because the operator must be able to report what really happened. The
 * expected-vs-selected comparison appears only after a choice is made, and it
 * states no verdict: compliance is decided by `POST /verify` on the backend.
 */
export function ActualRouteSelector({ data, onVerify, isVerifying }: ActualRouteSelectorProps) {
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null)
  const { valid_routes, route_meta, decision } = data.analysis
  const expectedMeta = resolveStream(decision?.expected_route, route_meta)
  const selectedMeta = selectedRoute ? resolveStream(selectedRoute, route_meta) : null

  return (
    <div className="space-y-5">
      <div>
        <div className="t-eyebrow">Verify</div>
        <h2 className="t-display mt-1">Which bin did you actually use?</h2>
        <p className="mt-1 t-body">
          Record the bin you used. The system compares it with the recommended bin.
        </p>
      </div>

      <div
        role="radiogroup"
        aria-label="Bin actually used"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4"
      >
        {valid_routes.map((route) => {
          const meta = resolveStream(route, route_meta)
          const isSelected = selectedRoute === route
          return (
            <button
              key={route}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={isVerifying}
              onClick={() => setSelectedRoute(route)}
              className={`group relative flex min-h-[136px] flex-col items-center justify-center gap-2 rounded-xl border-2 bg-card p-4 transition-all
                ${isSelected
                  ? "border-primary shadow-lift -translate-y-0.5"
                  : "border-border hover:border-primary/40 hover:shadow-card"}
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
                disabled:cursor-not-allowed disabled:opacity-60`}
              style={isSelected ? { boxShadow: `0 0 0 3px ${meta.hex}22` } : undefined}
            >
              {/* Selection is marked with a glyph as well as colour. */}
              {isSelected && (
                <span
                  aria-hidden
                  className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                >
                  <Check className="h-3.5 w-3.5" />
                </span>
              )}
              <WasteBin hex={meta.hex} size="sm" />
              <span className="break-words text-center text-sm font-bold leading-tight text-foreground">
                {meta.label}
              </span>
              {meta.category && (
                <span className="break-words text-center text-[11px] leading-tight text-muted-foreground">
                  {meta.category}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Expected vs selected — a comparison, NOT a verdict. */}
      {selectedMeta && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-secondary/50 px-5 py-4">
          <div className="flex items-center gap-4 sm:gap-6">
            <BinRef caption="Recommended" hex={expectedMeta.hex} label={expectedMeta.label} />
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/50" aria-hidden />
            <BinRef caption="You used" hex={selectedMeta.hex} label={selectedMeta.label} />
          </div>
          <p className="t-meta max-w-[16rem]">
            Compliance is determined when you check, not by this screen.
          </p>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          size="lg"
          className="h-12 w-full text-base font-semibold sm:w-auto sm:min-w-[240px]"
          disabled={!selectedRoute || isVerifying}
          onClick={() => selectedRoute && onVerify(selectedRoute)}
        >
          {isVerifying ? (
            <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Checking compliance…</>
          ) : (
            "Check compliance"
          )}
        </Button>
      </div>
    </div>
  )
}

function BinRef({ caption, hex, label }: { caption: string; hex: string; label: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="h-7 w-7 shrink-0 rounded-md ring-1 ring-black/10"
        style={{ backgroundColor: hex }}
      />
      <span className="leading-tight">
        <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
          {caption}
        </span>
        <span className="block text-sm font-bold text-foreground">{label}</span>
      </span>
    </div>
  )
}
