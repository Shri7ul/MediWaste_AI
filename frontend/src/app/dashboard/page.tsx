"use client"
import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api/client"
import { AnalyticsData } from "@/lib/types/api"
import { resolveStream } from "@/lib/waste"
import { Button } from "@/components/ui/button"
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LabelList,
} from "recharts"
import {
  ShieldCheck, ShieldAlert, CheckCircle2, AlertCircle, Layers, FileSearch, RefreshCw, AlertTriangle,
} from "lucide-react"

const CHART_TOOLTIP = {
  contentStyle: {
    backgroundColor: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "0.5rem",
    color: "hsl(var(--foreground))",
    fontSize: "12px",
  },
  cursor: { fill: "hsl(var(--muted))", opacity: 0.4 },
} as const

export default function DashboardPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.analytics()
      setData(res.analytics)
    } catch (e: any) {
      setError(e?.message || "Analytics service is unavailable.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const wasteViolations = useMemo(
    () => toSortedBars(data?.violations_by_waste_type),
    [data]
  )
  const routeViolations = useMemo(
    () => toSortedBars(data?.violations_by_route),
    [data]
  )
  const wardPerformance = useMemo(() => {
    if (!data?.by_ward) return []
    return Object.entries(data.by_ward)
      .map(([name, b]) => ({
        name,
        total: b.total,
        compliance: b.correct + b.violations > 0
          ? Math.round((b.correct / (b.correct + b.violations)) * 100)
          : null,
      }))
      .sort((a, b) => (b.compliance ?? -1) - (a.compliance ?? -1))
  }, [data])

  // ERROR
  if (error) {
    return (
      <div className="mx-auto mt-10 max-w-md rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
        <AlertTriangle className="mx-auto h-9 w-9 text-destructive" />
        <h2 className="mt-3 text-lg font-semibold text-foreground">Analytics unavailable</h2>
        <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        <Button onClick={load} variant="outline" className="mt-5">
          <RefreshCw className="mr-2 h-4 w-4" /> Retry
        </Button>
      </div>
    )
  }

  // LOADING
  if (loading || !data) {
    return (
      <div className="mx-auto max-w-7xl animate-pulse space-y-8">
        <div className="h-9 w-72 rounded bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-32 rounded-2xl bg-muted" />)}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-80 rounded-2xl bg-muted" />
          <div className="h-80 rounded-2xl bg-muted" />
        </div>
      </div>
    )
  }

  // EMPTY
  if (data.total_events === 0) {
    return (
      <div className="mx-auto mt-16 max-w-lg rounded-2xl border border-border bg-card p-12 text-center shadow-soft">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
          <FileSearch className="h-8 w-8 text-primary" />
        </div>
        <h2 className="mt-5 text-xl font-bold tracking-tight text-foreground">No audit data yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Compliance analytics appear here once waste items have been analyzed and verified.
        </p>
        <Button asChild className="mt-6">
          <a href="/scan">Analyze waste</a>
        </Button>
      </div>
    )
  }

  const complianceData = [
    { name: "Correct", value: data.correct, color: "#0f9d6b" },
    { name: "Violation", value: data.violations, color: "hsl(var(--destructive))" },
    { name: "Review / Pending", value: data.review_required + data.pending_verification, color: "#d97706" },
  ].filter((d) => d.value > 0)

  const complianceLabel = data.compliance_rate != null ? `${data.compliance_rate}%` : "—"

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <Header verified={data.verified} />
      <KpiRow data={data} complianceLabel={complianceLabel} />
      <ChartsGrid
        complianceData={complianceData}
        complianceLabel={complianceLabel}
        verified={data.verified}
        wasteViolations={wasteViolations}
        routeViolations={routeViolations}
        wardPerformance={wardPerformance}
      />
      <p className="text-xs text-muted-foreground">
        All figures are computed live from real audit events. Compliance rate is measured over verified
        events ({data.verified}); a value of “—” means no events have been verified yet.
      </p>
    </div>
  )
}

function toSortedBars(obj?: Record<string, number>) {
  if (!obj) return [] as { name: string; value: number }[]
  return Object.entries(obj)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
}

function Header({ verified }: { verified: number }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Compliance &amp; waste segregation performance
        </p>
      </div>
      <span className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        <Layers className="h-3.5 w-3.5" />
        {verified} verified {verified === 1 ? "event" : "events"}
      </span>
    </div>
  )
}

function KpiRow({ data, complianceLabel }: { data: AnalyticsData; complianceLabel: string }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {/* Dominant: compliance rate */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.06] p-5 shadow-card sm:col-span-2 lg:col-span-1">
        <div className="flex items-center gap-2 text-primary">
          <ShieldCheck className="h-4 w-4" />
          <span className="text-[11px] font-bold uppercase tracking-widest">Compliance rate</span>
        </div>
        <div className="mt-3 text-5xl font-black tabular-nums leading-none text-primary">{complianceLabel}</div>
        <p className="mt-2 text-xs text-muted-foreground">
          {data.compliance_rate != null
            ? `${data.correct} correct of ${data.verified} verified`
            : "Awaiting verified events"}
        </p>
      </div>

      <KpiCard label="Violations" value={data.violations} tone="destructive" icon={<ShieldAlert className="h-4 w-4" />} />
      <KpiCard label="Correct" value={data.correct} tone="success" icon={<CheckCircle2 className="h-4 w-4" />} />
      <KpiCard label="Review required" value={data.review_required} tone="warning" icon={<AlertCircle className="h-4 w-4" />} />
      <KpiCard label="Total events" value={data.total_events} tone="muted" icon={<Layers className="h-4 w-4" />} />
    </div>
  )
}

const TONE: Record<string, { text: string; icon: string }> = {
  destructive: { text: "text-destructive", icon: "text-destructive" },
  success: { text: "text-success", icon: "text-success" },
  warning: { text: "text-warning", icon: "text-warning" },
  muted: { text: "text-foreground", icon: "text-muted-foreground" },
}

function KpiCard({ label, value, tone, icon }: { label: string; value: number; tone: keyof typeof TONE | string; icon: React.ReactNode }) {
  const t = TONE[tone] ?? TONE.muted
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">{label}</span>
        <span className={t.icon}>{icon}</span>
      </div>
      <div className={`mt-3 text-4xl font-bold tabular-nums ${t.text}`}>{value}</div>
    </div>
  )
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <div className="mb-4">
        <h2 className="text-sm font-semibold tracking-tight text-foreground">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-56 items-center justify-center text-center text-sm text-muted-foreground">
      {label}
    </div>
  )
}

function ChartsGrid({
  complianceData, complianceLabel, verified, wasteViolations, routeViolations, wardPerformance,
}: {
  complianceData: { name: string; value: number; color: string }[]
  complianceLabel: string
  verified: number
  wasteViolations: { name: string; value: number }[]
  routeViolations: { name: string; value: number }[]
  wardPerformance: { name: string; total: number; compliance: number | null }[]
}) {
  const barHeight = (n: number) => Math.max(160, n * 44 + 40)
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Compliance overview */}
      <ChartCard title="Compliance overview" subtitle="Distribution of verified & pending outcomes">
        {complianceData.length > 0 ? (
          <div className="relative h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={complianceData} cx="50%" cy="50%" innerRadius={68} outerRadius={92} paddingAngle={3} dataKey="value" stroke="none">
                  {complianceData.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip {...CHART_TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-black tabular-nums text-foreground">{complianceLabel}</span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Compliance</span>
            </div>
          </div>
        ) : (
          <EmptyChart label="No verified outcomes yet." />
        )}
        <div className="mt-4 flex flex-wrap justify-center gap-4">
          {complianceData.map((e) => (
            <span key={e.name} className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: e.color }} />
              {e.name} · <span className="font-semibold tabular-nums text-foreground">{e.value}</span>
            </span>
          ))}
        </div>
      </ChartCard>

      {/* Violations by waste type */}
      <ChartCard title="Violations by waste type" subtitle="Where mis-segregation happens most">
        {wasteViolations.length > 0 ? (
          <ResponsiveContainer width="100%" height={barHeight(wasteViolations.length)}>
            <BarChart data={wasteViolations} layout="vertical" margin={{ top: 0, right: 28, left: 8, bottom: 0 }}>
              <XAxis type="number" hide domain={[0, "dataMax"]} allowDecimals={false} />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={128}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
              <Tooltip {...CHART_TOOLTIP} />
              <Bar dataKey="value" fill="hsl(var(--destructive))" radius={[0, 6, 6, 0]} barSize={22}>
                <LabelList dataKey="value" position="right" className="fill-foreground" style={{ fontSize: 12, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart label="No violations recorded — every item was segregated correctly." />
        )}
      </ChartCard>

      {/* Violations by disposal route */}
      <ChartCard title="Violations by disposal route" subtitle="Actual (incorrect) bin chosen">
        {routeViolations.length > 0 ? (
          <ResponsiveContainer width="100%" height={barHeight(routeViolations.length)}>
            <BarChart data={routeViolations} layout="vertical" margin={{ top: 0, right: 28, left: 8, bottom: 0 }}>
              <XAxis type="number" hide domain={[0, "dataMax"]} allowDecimals={false} />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={128}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
              <Tooltip {...CHART_TOOLTIP} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={22}>
                {routeViolations.map((r) => (
                  <Cell key={r.name} fill={resolveStream(r.name, undefined).hex} />
                ))}
                <LabelList dataKey="value" position="right" className="fill-foreground" style={{ fontSize: 12, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart label="No route violations recorded." />
        )}
      </ChartCard>

      {/* Ward performance */}
      <ChartCard title="Ward performance" subtitle="Compliance rate by ward (verified events)">
        {wardPerformance.length > 0 ? (
          <div className="space-y-4">
            {wardPerformance.map((w) => (
              <div key={w.name}>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">{w.name}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {w.compliance != null ? `${w.compliance}%` : "—"}
                    <span className="ml-2 text-xs text-muted-foreground/70">({w.total})</span>
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      w.compliance == null ? "bg-muted-foreground/30"
                        : w.compliance >= 90 ? "bg-success"
                        : w.compliance >= 70 ? "bg-warning"
                        : "bg-destructive"
                    }`}
                    style={{ width: `${w.compliance ?? 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyChart label="No ward-level data captured yet." />
        )}
      </ChartCard>
    </div>
  )
}
