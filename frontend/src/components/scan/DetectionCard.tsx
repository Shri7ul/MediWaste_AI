"use client"
import { AnalyzeResponse } from "@/lib/types/api"
import { apiAsset } from "@/lib/api/client"
import { ScanLine } from "lucide-react"

/**
 * Secondary, supporting card: what the vision model saw. Deliberately quieter
 * than ExpectedRouteCard — the operator's decision is the route, not the label.
 */
export function DetectionCard({ data }: { data: AnalyzeResponse }) {
  const { primary } = data.analysis
  const conf = Math.round((primary?.confidence || 0) * 100)
  const imageUrl = apiAsset(data.image_url)

  return (
    <section
      aria-label="Detected item"
      className="overflow-hidden rounded-2xl border border-border bg-card shadow-soft"
    >
      {imageUrl && (
        <div className="relative aspect-[4/3] bg-slate-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={primary?.item || "captured waste item"}
            className="h-full w-full object-cover"
          />
        </div>
      )}
      <div className="p-5">
        <div className="flex items-center gap-1.5 t-eyebrow">
          <ScanLine className="h-3.5 w-3.5" aria-hidden /> Item scanned
        </div>
        <h3 className="t-display mt-1">{primary?.item || "Unrecognised"}</h3>
        <p className="t-meta mt-1">Detection confidence {conf}%</p>
      </div>
    </section>
  )
}
