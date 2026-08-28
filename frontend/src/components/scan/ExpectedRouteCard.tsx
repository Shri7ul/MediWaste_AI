import { Card, CardContent } from "@/components/ui/card"
import { AnalyzeResponse } from "@/lib/types/api"
import { WasteBin } from "@/components/ui/waste-bin"
import { resolveStream, readableInk } from "@/lib/waste"
import { ArrowDownToLine } from "lucide-react"

export function ExpectedRouteCard({ data }: { data: AnalyzeResponse }) {
  const { decision, route_meta } = data.analysis
  const route = decision?.expected_route || "UNKNOWN"
  const meta = resolveStream(route, route_meta)

  return (
    <Card className="shadow-card border-border/70 overflow-hidden">
      <div className="bg-secondary/60 px-5 py-3 border-b border-border/70 flex items-center gap-2">
        <ArrowDownToLine className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold text-foreground">Recommended bin</span>
      </div>
      <CardContent className="pt-6 text-center space-y-4">
        <div className="mx-auto flex justify-center">
          <WasteBin hex={meta.hex} label={meta.label} size="lg" />
        </div>
        <div className="space-y-1">
          <div
            className="inline-flex items-center rounded-full px-3 py-1 text-sm font-bold"
            style={{ backgroundColor: meta.hex, color: readableInk(meta.hex) }}
          >
            {meta.label} bin
          </div>
          <div className="text-2xl font-bold tracking-tight text-foreground pt-1">
            {meta.category || decision?.waste_type}
          </div>
          <div className="text-sm text-muted-foreground">
            Policy {decision?.rule_id} · v{decision?.policy_version}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
