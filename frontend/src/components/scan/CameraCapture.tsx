"use client"
import { useState, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Camera, Upload, X, RefreshCw, ImageUp } from 'lucide-react'

interface CameraCaptureProps {
  onCapture: (file: File) => void;
}

export function CameraCapture({ onCapture }: CameraCaptureProps) {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const startCamera = async () => {
    setError(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera not supported on this device — please upload an image instead.")
      return
    }
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      setStream(mediaStream)
      if (videoRef.current) videoRef.current.srcObject = mediaStream
    } catch {
      setError("Camera access was blocked. You can upload an image instead.")
    }
  }

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      setStream(null)
    }
  }, [stream])

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

  if (stream) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-slate-900 border border-border shadow-card">
        <video ref={videoRef} autoPlay playsInline className="w-full max-h-[62vh] object-cover" />
        <div className="pointer-events-none absolute inset-8 rounded-xl border-2 border-white/40" />
        <div className="absolute bottom-5 left-0 right-0 flex items-center justify-center gap-5">
          <Button variant="secondary" size="icon" className="rounded-full" onClick={stopCamera}>
            <X className="h-5 w-5" />
          </Button>
          <button
            onClick={captureStill}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-slate-900 shadow-lift ring-4 ring-white/30 transition-transform active:scale-95"
            aria-label="Capture photo"
          >
            <Camera className="h-6 w-6" />
          </button>
          <Button variant="secondary" size="icon" className="rounded-full" onClick={startCamera}>
            <RefreshCw className="h-5 w-5" />
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border-2 border-dashed border-border bg-card p-8 sm:p-12 shadow-soft">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
          <ImageUp className="h-8 w-8" />
        </div>
        <h2 className="mt-5 text-xl font-bold tracking-tight text-foreground">
          Capture the waste item
        </h2>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          Use your camera or upload a photo. We&apos;ll identify the item and tell you
          which bin it belongs in.
        </p>

        <div className="mt-6 flex w-full flex-col sm:flex-row gap-3 sm:justify-center">
          <Button onClick={startCamera} size="lg" className="w-full sm:w-auto">
            <Camera className="mr-2 h-5 w-5" /> Scan waste
          </Button>
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            size="lg"
            className="w-full sm:w-auto"
          >
            <Upload className="mr-2 h-5 w-5" /> Upload image
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept="image/jpeg,image/png,image/jpg"
            className="hidden"
          />
        </div>

        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      </div>
    </div>
  )
}
