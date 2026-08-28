"use client"
import { Card, CardContent } from "@/components/ui/card"
import { AnalyzeResponse } from "@/lib/types/api"
import { apiAsset } from "@/lib/api/client"
import { ScanLine } from "lucide-react"

export function DetectionCard({ data }: { data: AnalyzeResponse }) {
  const { primary } = data.analysis
  const conf = Math.round((primary?.confidence || 0) * 100)
  const imageUrl = apiAsset(data.image_url)

  return (
    <Card className="overflow-hidden shadow-card border-border/70">
      {imageUrl && (
        <div className="relative bg-slate-100 aspect-[4/3]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={primary?.item || "captured waste item"}
            className="h-full w-full object-cover"
          />
        </div>
      )}
      <CardContent className="pt-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary">
          <ScanLine className="h-3.5 w-3.5" /> Detected item
        </div>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
          {primary?.item || "Unrecognised"}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Model confidence {conf}%
        </p>
      </CardContent>
    </Card>
  )
}
