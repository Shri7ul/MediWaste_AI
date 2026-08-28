"use client"
import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { AnalyzeResponse } from "@/lib/types/api"
import { WasteBin } from "@/components/ui/waste-bin"
import { resolveStream } from "@/lib/waste"
import { Check, Loader2 } from "lucide-react"

interface ActualRouteSelectorProps {
  data: AnalyzeResponse;
  onVerify: (route: string) => void;
  isVerifying: boolean;
}

export function ActualRouteSelector({ data, onVerify, isVerifying }: ActualRouteSelectorProps) {
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null)
  const { valid_routes, route_meta } = data.analysis

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold tracking-tight text-foreground">
          Where did you place the item?
        </h3>
        <p className="text-muted-foreground mt-1">
          Tap the bin you actually used. We&apos;ll check it against the recommended bin.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
        {valid_routes.map((route) => {
          const meta = resolveStream(route, route_meta)
          const isSelected = selectedRoute === route
          return (
            <button
              key={route}
              type="button"
              disabled={isVerifying}
              onClick={() => setSelectedRoute(route)}
              className={`group relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 bg-card p-4 min-h-[132px] transition-all
                ${isSelected
                  ? "border-primary shadow-lift -translate-y-0.5"
                  : "border-border hover:border-primary/40 hover:shadow-card"}
                disabled:opacity-60 disabled:cursor-not-allowed`}
              style={isSelected ? { boxShadow: `0 0 0 3px ${meta.hex}22` } : undefined}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Check className="h-3.5 w-3.5" />
                </span>
              )}
              <WasteBin hex={meta.hex} size="sm" />
              <span className="text-sm font-semibold text-center leading-tight text-foreground">
                {meta.label}
              </span>
              {meta.category && (
                <span className="text-[11px] text-muted-foreground text-center leading-tight">
                  {meta.category}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="flex justify-end pt-2">
        <Button
          size="lg"
          className="w-full sm:w-auto min-w-[220px]"
          disabled={!selectedRoute || isVerifying}
          onClick={() => selectedRoute && onVerify(selectedRoute)}
        >
          {isVerifying ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking…</>
          ) : (
            "Check compliance"
          )}
        </Button>
      </div>
    </div>
  )
}
