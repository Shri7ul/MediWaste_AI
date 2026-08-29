"use client"
import { useEffect, useState } from "react"
import { Smartphone } from "lucide-react"
import { encodeQr, qrPath } from "@/lib/qr"

/**
 * Desktop-only "open this on your phone" card for the exhibition screen.
 *
 * WHAT IT IS NOT
 * It is not a feature of the product and it is not part of the scan flow. It
 * exists so a judge standing at the laptop can reach the same app from their own
 * phone without typing an address, and it is hidden below `lg` — a judge already
 * holding the phone does not need a QR code to their own screen.
 *
 * HONESTY RULES (both matter more than the convenience)
 *  - The target is derived from `window.location`, never from a hardcoded host,
 *    so the QR always encodes an address this browser is actually serving from.
 *  - When that address is loopback it is useless to another device, so NO QR is
 *    drawn at all; the card explains what to change instead. A scannable code
 *    pointing at `localhost` would send the judge to their own phone.
 *
 * The plain text URL is always shown, so the card degrades to something usable
 * even if the code cannot be rendered.
 */

/** Hosts that only resolve on the machine running the browser. */
const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"])

interface Origin {
  target: string
  loopback: boolean
  insecure: boolean
}

export function PhoneHandoff() {
  // `window` does not exist during server rendering, so this resolves after mount.
  const [origin, setOrigin] = useState<Origin | null>(null)

  useEffect(() => {
    const { origin: base, hostname, protocol } = window.location
    setOrigin({
      target: `${base.replace(/\/+$/, "")}/scan`,
      loopback: LOOPBACK.has(hostname.toLowerCase()),
      insecure: protocol === "http:",
    })
  }, [])

  if (!origin) return null

  const code = origin.loopback ? null : encodeQr(origin.target)

  return (
    <section
      aria-labelledby="phone-handoff-heading"
      className="hidden rounded-xl border border-border bg-secondary/40 p-5 lg:block"
    >
      <div className="flex items-start gap-6">
        {code ? (
          <svg
            role="img"
            aria-label={`QR code for ${origin.target}`}
            viewBox={`0 0 ${code.size + 8} ${code.size + 8}`}
            className="h-[132px] w-[132px] shrink-0 rounded-lg bg-white p-1 ring-1 ring-black/10"
            shapeRendering="crispEdges"
          >
            <path d={qrPath(code)} fill="#0f172a" />
          </svg>
        ) : (
          <span
            aria-hidden
            className="flex h-[132px] w-[132px] shrink-0 items-center justify-center rounded-lg border border-dashed border-border bg-background"
          >
            <Smartphone className="h-8 w-8 text-muted-foreground/50" />
          </span>
        )}

        <div className="min-w-0 space-y-2">
          <div className="t-eyebrow">Exhibition</div>
          <h2 id="phone-handoff-heading" className="t-title">
            {code ? "Scan with your phone" : "Try this on your phone"}
          </h2>
          <p className="t-body">
            The phone runs the same scan, the same policy decision and the same
            compliance check as this screen. Nothing is simulated for mobile.
          </p>

          {/* Always shown: the code is a convenience, the address is the fallback. */}
          <p className="break-all font-mono text-sm font-semibold text-foreground">
            {origin.target}
          </p>

          {origin.loopback ? (
            <p className="t-meta">
              This page is being served from a loopback address, so the URL above
              only resolves on this laptop and no QR code is shown. Start the
              frontend on the network interface and reopen this page from the
              laptop&apos;s own LAN address to get a code another device can use —
              see the frontend README.
            </p>
          ) : (
            origin.insecure && (
              <p className="t-meta">
                Phone browsers only grant camera access on a secure origin. If the
                camera is blocked over plain HTTP, the phone can still use{" "}
                <span className="font-semibold">Upload photo</span> and the flow is
                identical.
              </p>
            )
          )}
        </div>
      </div>
    </section>
  )
}
