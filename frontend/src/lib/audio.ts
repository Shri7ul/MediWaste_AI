/**
 * Verification result audio.
 *
 * The verification feedback is two pre-generated WAV assets served as Next.js
 * static files from `public/audio/`:
 *   - CORRECT   → /audio/success.wav
 *   - VIOLATION → /audio/warning.wav
 * Every other compliance state (REVIEW_REQUIRED, PENDING_VERIFICATION,
 * INVALID_ROUTE, …) and every non-result phase stays silent, and a failed
 * `/verify` request never plays anything.
 *
 * Design notes:
 *  - ONE lazily-created, module-scoped HTMLAudioElement per asset is reused for
 *    the lifetime of the tab. Nothing is created per render; there is no
 *    third-party dependency and no generated audio.
 *  - Browsers gate audio playback behind a user gesture, so `unlockAudio()` is
 *    called synchronously inside the click handler (before any `await`) to prime
 *    the elements while the activation is still valid; the actual sound plays
 *    later, once the compliance result is committed.
 *  - Every entry point is a no-op on failure / on the server. Audio is purely
 *    supplementary feedback; the visual result is always authoritative.
 */

const ASSETS = {
  CORRECT: '/audio/success.wav',
  VIOLATION: '/audio/warning.wav',
} as const

type ResultKey = keyof typeof ASSETS

const elements: Partial<Record<ResultKey, HTMLAudioElement>> = {}

function getElement(key: ResultKey): HTMLAudioElement | null {
  if (typeof window === 'undefined' || typeof Audio === 'undefined') return null
  const existing = elements[key]
  if (existing) return existing
  try {
    const el = new Audio(ASSETS[key])
    el.preload = 'auto'
    elements[key] = el
    return el
  } catch {
    return null
  }
}

/**
 * Prime the result audio elements while a user gesture is still active. Call
 * this synchronously from the click handler that will later produce a result
 * (e.g. "Check compliance"), never from an effect or a timer. It only loads the
 * assets — it never produces sound.
 */
export function unlockAudio(): void {
  ;(Object.keys(ASSETS) as ResultKey[]).forEach((key) => {
    const el = getElement(key)
    if (!el) return
    try {
      el.load()
    } catch {
      /* priming is best-effort — never surface an error to the operator */
    }
  })
}

/**
 * Play the voice feedback for a committed compliance result. Fire-and-forget:
 * callers do not await it and never depend on it succeeding.
 *
 *   CORRECT   → success.wav
 *   VIOLATION → warning.wav
 *   anything else (REVIEW_REQUIRED, PENDING_VERIFICATION, INVALID_ROUTE, …)
 *             → silent, by design.
 */
export function playVerificationResult(status: string): void {
  if (status !== 'CORRECT' && status !== 'VIOLATION') return
  const el = getElement(status)
  if (!el) return
  try {
    el.currentTime = 0
    void el.play().catch(() => {})
  } catch {
    /* audio is optional feedback — never surface an error to the operator */
  }
}
