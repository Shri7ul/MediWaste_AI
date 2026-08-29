"use client"

import { createContext, useContext, useEffect, useMemo, useState } from "react"
import { StageId } from "@/lib/narrative"

/**
 * Lets the scan flow refine the narrative stage the rail highlights, because
 * SCAN, DECIDE and VERIFY all live at the same URL. Purely cosmetic: no
 * decision, request or persisted value depends on it.
 */
const StageContext = createContext<{
  override: StageId | null
  setOverride: (s: StageId | null) => void
}>({ override: null, setOverride: () => {} })

export function StageProvider({ children }: { children: React.ReactNode }) {
  const [override, setOverride] = useState<StageId | null>(null)
  const value = useMemo(() => ({ override, setOverride }), [override])
  return <StageContext.Provider value={value}>{children}</StageContext.Provider>
}

export function useStageOverride() {
  return useContext(StageContext).override
}

/** Publish the active stage while mounted; clears it on unmount. */
export function useSetStage(stage: StageId | null) {
  const { setOverride } = useContext(StageContext)
  useEffect(() => {
    setOverride(stage)
    return () => setOverride(null)
  }, [stage, setOverride])
}
