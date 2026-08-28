/**
 * Tiny Web Audio helper for UI confirmation tones.
 *
 * Design notes:
 *  - ONE lazily-created, module-scoped AudioContext is reused for the lifetime of
 *    the tab. Nothing is created per render, and there is no audio asset, no
 *    network request, and no third-party dependency.
 *  - Browsers only allow an AudioContext to start from a user gesture, so
 *    `unlockAudio()` is called synchronously inside a click handler (before any
 *    `await`), and the tone itself is played later when the result is committed.
 *  - Every entry point is a no-op on failure / on the server. Audio is purely
 *    supplementary feedback; the visual result is always authoritative.
 */

type AudioCtor = typeof AudioContext

let ctx: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (ctx) return ctx
  const Ctor: AudioCtor | undefined =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext
  if (!Ctor) return null
  try {
    ctx = new Ctor()
  } catch {
    return null
  }
  return ctx
}

/**
 * Create/resume the shared AudioContext while a user gesture is still active.
 * Call this synchronously from the click handler that will later produce a tone
 * (e.g. "Check compliance"), never from an effect or a timer.
 */
export function unlockAudio(): void {
  const ac = getAudioContext()
  if (!ac) return
  if (ac.state === 'suspended') {
    void ac.resume().catch(() => {})
  }
}

/**
 * A single short, subtle confirmation beep (~120 ms sine tone with a soft
 * attack/decay envelope so it clicks neither on nor off). Fire-and-forget:
 * callers do not await it and never depend on it succeeding.
 */
export function playVerificationBeep(): void {
  const ac = getAudioContext()
  if (!ac) return
  try {
    if (ac.state === 'suspended') void ac.resume().catch(() => {})

    const now = ac.currentTime
    const duration = 0.12 // seconds — short enough to read as a confirmation
    const peak = 0.09 // conservative level: audible, not startling

    const osc = ac.createOscillator()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, now) // A5 — clean, neutral, non-alarming

    const gain = ac.createGain()
    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(peak, now + 0.012) // soft attack
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration) // soft decay

    osc.connect(gain)
    gain.connect(ac.destination)

    osc.start(now)
    osc.stop(now + duration + 0.02)
    osc.onended = () => {
      try {
        osc.disconnect()
        gain.disconnect()
      } catch {
        /* nothing to clean up */
      }
    }
  } catch {
    /* audio is optional feedback — never surface an error to the operator */
  }
}
