"use client"
import { useEffect, useState } from 'react'
import { Building2, AlertCircle, Loader2 } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api/client'
import { Ward } from '@/lib/types/api'

/**
 * Compact WARD context selector for the scan entry screen.
 *
 * The options come ONLY from the backend facility registry (`GET /facility/wards`)
 * — no ward name is hardcoded here, so the Dashboard's per-ward analytics always
 * aggregate ids the facility actually configured. There is no default selection
 * on purpose: an audit event must never be attributed to an arbitrary ward.
 *
 * Ward is operational CONTEXT only. It is attached to the audit event and never
 * feeds the deterministic policy decision or the expected route.
 */
interface WardSelectorProps {
  value: string | null
  onChange: (wardId: string) => void
  /** Locked once analysis is under way so in-flight context can't be edited. */
  disabled?: boolean
}

export function WardSelector({ value, onChange, disabled }: WardSelectorProps) {
  const [wards, setWards] = useState<Ward[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.facilityWards()
      .then((r) => { if (!cancelled) setWards(r.wards || []) })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="mb-4 flex flex-col gap-2 rounded-xl border border-border bg-card px-4 py-3 shadow-soft sm:flex-row sm:items-center sm:gap-4">
      <div className="flex items-center gap-2 sm:shrink-0">
        <Building2 className="h-4 w-4 text-primary" />
        <label
          htmlFor="ward-select"
          className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground"
        >
          Ward
        </label>
      </div>

      {failed ? (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Ward list unavailable. Check that the MediWaste AI service is running.
        </p>
      ) : !wards ? (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading wards…
        </p>
      ) : (
        <>
          <Select value={value ?? undefined} onValueChange={onChange} disabled={disabled}>
            <SelectTrigger id="ward-select" className="h-9 sm:max-w-[16rem]">
              <SelectValue placeholder="Select ward" />
            </SelectTrigger>
            <SelectContent>
              {wards.map((w) => (
                <SelectItem key={w.id} value={w.id}>
                  {w.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!value && (
            <span className="text-xs text-muted-foreground">
              Required before analysis
            </span>
          )}
        </>
      )}
    </div>
  )
}
