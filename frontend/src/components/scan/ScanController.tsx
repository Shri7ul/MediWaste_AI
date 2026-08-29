"use client"
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CameraCapture } from './CameraCapture'
import { WardSelector } from './WardSelector'
import { AnalysisProgress } from './AnalysisProgress'
import { DetectionCard } from './DetectionCard'
import { ExpectedRouteCard } from './ExpectedRouteCard'
import { ActualRouteSelector } from './ActualRouteSelector'
import { ComplianceResult } from './ComplianceResult'
import { EvidenceSheet } from './EvidenceSheet'
import { api, ApiError } from '@/lib/api/client'
import { AnalyzeResponse, VerifyResponse } from '@/lib/types/api'
import { resolveStream } from '@/lib/waste'
import { unlockAudio, playVerificationResult } from '@/lib/audio'
import { useSetStage } from '@/components/layout/StageContext'
import { StageId } from '@/lib/narrative'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, Building2, FileSearch, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'

type FlowState = 'capture' | 'analyzing' | 'verifying' | 'result' | 'error'

// Which narrative stage each point in the flow belongs to. SCAN, DECIDE and
// VERIFY all share the /scan URL, so the rail is told explicitly.
const FLOW_STAGE: Record<FlowState, StageId> = {
  capture: 'scan',
  analyzing: 'decide',
  verifying: 'verify',
  result: 'verify',
  error: 'scan',
}

// Station is a fixed identifier for this exhibition terminal. Ward is chosen by
// the operator per scan (see WardSelector) — it is never defaulted here.
const STATION_ID = 'Station-1'

export function ScanController() {
  const [flowState, setFlowState] = useState<FlowState>('capture')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [analyzeData, setAnalyzeData] = useState<AnalyzeResponse | null>(null)
  const [verifyData, setVerifyData] = useState<VerifyResponse | null>(null)
  const [actualRoute, setActualRoute] = useState<string | null>(null)
  const [isVerifying, setIsVerifying] = useState(false)
  const [showEvidence, setShowEvidence] = useState(false)
  // The operator's current ward choice. Editable until an image is submitted, so
  // the LAST value selected before analysis is the one that is used.
  const [ward, setWard] = useState<string | null>(null)
  // The ward the in-flight event was actually created with. Snapshotted at
  // capture time so nothing that happens afterwards can change the ward the
  // audit event is verified under.
  const [eventWard, setEventWard] = useState<string | null>(null)

  const handleCapture = async (file: File) => {
    // Ward is required: an audit event must never be attributed to a ward the
    // operator did not choose. The capture buttons are disabled until then, so
    // this is a safety net rather than the primary gate.
    if (!ward) return
    const capturedWard = ward
    setEventWard(capturedWard)
    setFlowState('analyzing')
    setErrorMsg(null)
    const formData = new FormData()
    formData.append('image', file)
    formData.append('station', STATION_ID)
    formData.append('ward', capturedWard)
    try {
      const result = await api.analyze(formData)
      setAnalyzeData(result)
      setFlowState('verifying')
    } catch (e) {
      handleError(e)
    }
  }

  const handleVerify = async (route: string) => {
    if (!analyzeData) return
    // Prepare audio while the click's user activation is still valid (before any
    // await). No sound is produced here — the tone plays only once a compliance
    // result actually exists.
    unlockAudio()
    setActualRoute(route)
    setIsVerifying(true)
    try {
      const result = await api.verify({
        event_id: analyzeData.event_id,
        actual_route: route,
        station: STATION_ID,
        // The ward captured with this event — not whatever the selector shows now.
        ward: eventWard ?? undefined,
      })
      setVerifyData(result)
      setFlowState('result')
      // Exactly one result-specific voice cue per completed verification, played
      // only after the compliance result is committed: success.wav for CORRECT,
      // warning.wav for VIOLATION, silence for every other status. This lives in
      // the async click handler (not an effect), so re-renders, unrelated state
      // changes, StrictMode double-invocation and back/forward navigation cannot
      // replay it. Failures return above and stay silent. Purely supplementary —
      // ComplianceResult remains authoritative.
      playVerificationResult(result.verification.status)
    } catch (e) {
      handleError(e)
    } finally {
      setIsVerifying(false)
    }
  }

  // Maps backend/network failures to calm, plain-English operator messages.
  const handleError = (e: unknown) => {
    let msg = 'Something went wrong. Please try again.'
    if (e instanceof ApiError) {
      if (e.code === 'INVALID_WARD') {
        setErrorMsg('That ward is not configured for this facility. Please choose a ward from the list.')
        setFlowState('error')
        return
      }
      switch (e.status) {
        case 400:
          msg = 'That image could not be read. Please capture or upload a clear photo.'
          break
        case 404:
          msg = 'This scan is no longer available. Please start a new scan.'
          break
        case 409:
          msg = 'Please complete the current step before continuing.'
          break
        case 415:
          msg = 'Unsupported file type. Please use a JPG or PNG image.'
          break
        case 503:
          msg = 'The analysis service is temporarily unavailable. Please try again shortly.'
          break
        case 500:
          msg = 'The system could not analyse this item. Please try again or use a different photo.'
          break
        default:
          msg = e.message || msg
      }
    } else if (typeof navigator !== 'undefined' && !navigator.onLine) {
      msg = 'You appear to be offline. Check your connection and try again.'
    } else if (e instanceof Error && /fetch|network/i.test(e.message)) {
      msg = 'Cannot reach the MediWaste AI service. Please check that the backend is running.'
    }
    setErrorMsg(msg)
    setFlowState('error')
  }

  const reset = () => {
    setAnalyzeData(null)
    setVerifyData(null)
    setActualRoute(null)
    setErrorMsg(null)
    setIsVerifying(false)
    // The ward selection is an explicit operator choice and survives to the next
    // item (operators scan a run of items in one ward). The per-event snapshot is
    // cleared so nothing is carried onto a different event.
    setEventWard(null)
    setFlowState('capture')
  }

  const decision = analyzeData?.analysis.decision
  const expectedMeta = decision
    ? resolveStream(decision.expected_route, analyzeData!.analysis.route_meta)
    : null

  // Keeps the header rail in step with the flow (SCAN → DECIDE → VERIFY).
  useSetStage(FLOW_STAGE[flowState])

  // The ward stays on screen for the whole scan: once an event exists its
  // snapshot wins, otherwise the operator's current choice is echoed back.
  const shownWard = eventWard ?? ward

  return (
    <div className="w-full">
      {/* Persistent ward context — subtle, but never off-screen once chosen. */}
      {shownWard && flowState !== 'capture' && (
        <div className="mb-5 flex items-center gap-2 border-b border-border/70 pb-3">
          <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            Ward
          </span>
          <span className="font-mono text-sm font-semibold text-foreground">{shownWard}</span>
          {eventWard && (
            <span className="t-meta ml-auto hidden sm:inline">Recorded with this audit event</span>
          )}
        </div>
      )}

      {flowState === 'error' && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>We hit a problem</AlertTitle>
          <AlertDescription className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <span>{errorMsg}</span>
            <Button variant="outline" size="sm" onClick={reset} className="shrink-0">
              <RotateCcw className="mr-2 h-4 w-4" /> Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <AnimatePresence mode="wait">
        {flowState === 'capture' && (
          <motion.div key="capture" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <WardSelector value={ward} onChange={setWard} />
            <CameraCapture
              onCapture={handleCapture}
              disabled={!ward}
              disabledHint="Select the ward this waste came from, then capture or upload a photo."
            />
          </motion.div>
        )}

        {flowState === 'analyzing' && !analyzeData && (
          <motion.div key="analyzing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AnalysisProgress />
          </motion.div>
        )}

        {flowState === 'verifying' && analyzeData && !verifyData && (
          <motion.div
            key="verifying"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8"
          >
            <div className="lg:col-span-5 space-y-6">
              <ExpectedRouteCard data={analyzeData} />
              {expectedMeta && (
                <div className="rounded-xl border border-border bg-accent/50 p-4">
                  <p className="text-sm leading-relaxed text-foreground">
                    This looks like{' '}
                    <span className="font-semibold">{decision?.waste_type?.toLowerCase()}</span>{' '}
                    waste, which policy routes to the{' '}
                    <span className="font-semibold">{expectedMeta.label}</span> bin.
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowEvidence(true)}
                    className="mt-2 inline-flex items-center gap-1.5 rounded text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <FileSearch className="h-3.5 w-3.5" aria-hidden /> Why this route?
                  </button>
                </div>
              )}
              <DetectionCard data={analyzeData} />
            </div>
            <div className="lg:col-span-7">
              <ActualRouteSelector data={analyzeData} onVerify={handleVerify} isVerifying={isVerifying} />
            </div>
          </motion.div>
        )}

        {flowState === 'result' && verifyData && analyzeData && actualRoute && (
          <motion.div key="result" className="max-w-2xl mx-auto">
            <ComplianceResult
              verifyData={verifyData}
              analyzeData={analyzeData}
              actualRoute={actualRoute}
              onViewEvidence={() => setShowEvidence(true)}
              onContinue={reset}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <EvidenceSheet
        open={showEvidence}
        onOpenChange={setShowEvidence}
        analyzeData={analyzeData}
        verifyData={verifyData}
      />
    </div>
  )
}
