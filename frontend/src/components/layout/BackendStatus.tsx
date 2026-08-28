"use client"
import { useState, useEffect } from 'react'
import { api } from '@/lib/api/client'

export function BackendStatus() {
  const [status, setStatus] = useState<'ready' | 'offline' | 'checking'>('checking')

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        await api.health()
        if (mounted) setStatus('ready')
      } catch (e) {
        if (mounted) setStatus('offline')
      }
    }
    check()
    const interval = setInterval(check, 30000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium shadow-soft">
      <span
        className={`h-2 w-2 rounded-full ${
          status === 'ready'
            ? 'bg-success'
            : status === 'offline'
            ? 'bg-destructive'
            : 'bg-muted-foreground/50 animate-pulse-soft'
        }`}
      />
      <span className="hidden sm:inline-block text-foreground">
        {status === 'ready' ? 'System Ready' : status === 'offline' ? 'Backend Offline' : 'Connecting…'}
      </span>
    </div>
  )
}
