"use client"
import { useState, useRef, useCallback, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Camera, Upload, X, RefreshCw, ImageUp, CameraOff } from 'lucide-react'

interface CameraCaptureProps {
  onCapture: (file: File) => void;
  /** Blocks capture/upload until required scan context (ward) is chosen. */
  disabled?: boolean;
  /** Shown in place of the normal hint when `disabled` is true. */
  disabledHint?: string;
}

/**
 * Capture surface for the scan flow — one still image, on request only.
 *
 * Phone notes:
 *  - The rear camera is requested (`facingMode: "environment"`); a phone's front
 *    camera is useless for inspecting a waste item.
 *  - Nothing is streamed to the backend. A single frame is drawn to a canvas when
 *    the operator taps the shutter, and that JPEG is what `/analyze` receives.
 *  - Camera access can fail for reasons the operator cannot fix (no permission,
 *    or an insecure LAN origin where the browser blocks `getUserMedia` outright).
 *    That is treated as a normal, expected path: plain-English copy plus an
 *    immediate `Upload photo` action, never an exception.
 */
export function CameraCapture({ onCapture, disabled, disabledHint }: CameraCaptureProps) {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [starting, setStarting] = useState(false)
  const [cameraBlocked, setCameraBlocked] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  // The <video> element does not exist until a stream has been set, so the track
  // must be attached after that render — not inline in startCamera().
  useEffect(() => {
    const v = videoRef.current
    if (v && stream) {
      v.srcObject = stream
      v.play().catch(() => { /* autoplay is best-effort; the muted attribute covers iOS */ })
    }
  }, [stream])

  // Release the camera if the operator navigates away mid-preview.
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
  }, [])

  const startCamera = async () => {
    setCameraBlocked(false)
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraBlocked(true)
      return
    }
    setStarting(true)
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      streamRef.current = mediaStream
      setStream(mediaStream)
    } catch {
      setCameraBlocked(true)
    } finally {
      setStarting(false)
    }
  }

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setStream(null)
  }, [])

  const captureStill = () => {
    if (!videoRef.current) return
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0)
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], 'capture.jpg', { type: 'image/jpeg' })
          stopCamera()
          onCapture(file)
        }
      }, 'image/jpeg', 0.9)
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) onCapture(e.target.files[0])
  }

  const openFilePicker = () => fileInputRef.current?.click()

  /** One hidden input serves every upload entry point on this screen. */
  const fileInput = (
    <input
      type="file"
      ref={fileInputRef}
      onChange={handleFileUpload}
      accept="image/jpeg,image/png,image/jpg"
      className="hidden"
      disabled={disabled}
    />
  )

  // ---------------------------------------------------------------- live camera
  if (stream) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-border bg-slate-900 shadow-card">
        {/* Tall on a phone so the item fills the frame; unchanged proportions on desktop. */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="h-[62vh] w-full object-cover sm:h-auto sm:max-h-[62vh]"
        />
        {/* Framing guide: one clean rectangle, no decorative overlays. */}
        <div className="pointer-events-none absolute inset-6 rounded-xl border-2 border-white/40 sm:inset-8" />
        <p className="pointer-events-none absolute left-0 right-0 top-4 px-4 text-center text-[11px] font-bold uppercase tracking-[0.18em] text-white/80">
          Fill the frame with the item
        </p>
        <div className="absolute bottom-6 left-0 right-0 flex items-center justify-center gap-8 sm:gap-6">
          <Button
            variant="secondary"
            size="icon"
            className="h-11 w-11 rounded-full"
            onClick={stopCamera}
            aria-label="Close camera"
          >
            <X className="h-5 w-5" aria-hidden />
          </Button>
          <button
            type="button"
            onClick={captureStill}
            className="flex h-20 w-20 items-center justify-center rounded-full bg-white text-slate-900 shadow-lift ring-4 ring-white/30 transition-transform active:scale-95 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white"
            aria-label="Capture waste"
          >
            <Camera className="h-7 w-7" aria-hidden />
          </button>
          <Button
            variant="secondary"
            size="icon"
            className="h-11 w-11 rounded-full"
            onClick={startCamera}
            aria-label="Restart camera"
          >
            <RefreshCw className="h-5 w-5" aria-hidden />
          </Button>
        </div>
        {fileInput}
      </div>
    )
  }

  // ------------------------------------------------- camera unavailable/blocked
  if (cameraBlocked) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 text-center shadow-soft sm:p-10">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <CameraOff className="h-7 w-7" aria-hidden />
        </div>
        <h2 className="t-display mt-4">Camera access isn&apos;t available</h2>
        <p role="alert" className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
          You can upload a photo instead. The scan, policy decision and compliance
          check are exactly the same either way.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button onClick={openFilePicker} size="lg" disabled={disabled} className="h-12 w-full sm:w-auto">
            <Upload className="mr-2 h-5 w-5" aria-hidden /> Upload photo
          </Button>
          <Button variant="ghost" onClick={startCamera} size="lg" className="h-12 w-full sm:w-auto">
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Try camera again
          </Button>
        </div>
        {fileInput}
      </div>
    )
  }

  // ----------------------------------------------------------------- idle state
  return (
    <div className="rounded-2xl border-2 border-dashed border-border bg-card p-6 shadow-soft sm:p-12">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
          <ImageUp className="h-8 w-8" aria-hidden />
        </div>
        <h2 className="t-display mt-5">Capture the waste item</h2>
        <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
          {disabled && disabledHint
            ? disabledHint
            : <>Point the camera at the item, or upload a photo. We&apos;ll identify it
              and tell you which bin it belongs in.</>}
        </p>

        {/* One primary action. Upload stays available but is visibly secondary. */}
        <div className="mt-6 w-full sm:w-auto">
          <Button
            onClick={startCamera}
            size="lg"
            disabled={disabled || starting}
            className="h-12 w-full text-base sm:w-auto sm:min-w-[240px]"
          >
            <Camera className="mr-2 h-5 w-5" aria-hidden />
            {starting ? 'Requesting camera access…' : 'Start scan'}
          </Button>
        </div>
        <Button
          variant="ghost"
          onClick={openFilePicker}
          disabled={disabled}
          className="mt-2 h-11 w-full text-muted-foreground sm:w-auto"
        >
          <Upload className="mr-2 h-4 w-4" aria-hidden /> Upload a photo instead
        </Button>
        {fileInput}
      </div>
    </div>
  )
}
