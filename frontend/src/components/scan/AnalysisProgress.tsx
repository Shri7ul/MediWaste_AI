"use client"
import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2 } from 'lucide-react'

export function AnalysisProgress() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const timers = [
      setTimeout(() => setStage(1), 900),
      setTimeout(() => setStage(2), 2200),
      setTimeout(() => setStage(3), 3800),
    ]
    return () => timers.forEach(clearTimeout)
  }, [])

  const stages = [
    "Identifying the item",
    "Checking segregation policy",
    "Retrieving supporting evidence",
    "Preparing explanation",
  ]

  return (
    <div className="rounded-2xl border border-border bg-card p-10 shadow-soft">
      <div className="mx-auto max-w-sm space-y-4">
        <div className="flex items-center gap-2 text-primary font-semibold">
          <Loader2 className="h-5 w-5 animate-spin" /> Analyzing waste…
        </div>
        {stages.map((text, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 transition-opacity duration-500 ${
              i <= stage ? 'opacity-100' : 'opacity-40'
            }`}
          >
            {i < stage ? (
              <CheckCircle2 className="h-5 w-5 text-success" />
            ) : i === stage ? (
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
            ) : (
              <span className="h-5 w-5 rounded-full border-2 border-muted" />
            )}
            <span className={i <= stage ? 'text-foreground' : 'text-muted-foreground'}>
              {text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
