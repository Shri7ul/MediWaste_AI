"use client"
import { useEffect, useState } from "react"
import { Smartphone } from "lucide-react"
import { encodeQr, qrPath } from "@/lib/qr"
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

/**
 * Desktop-only "open this on your phone" affordance for the exhibition screen.
 *
 * WHAT IT IS NOT
 * It is not a feature of the product and it is not part of the scan flow. It
 * exists so a judge standing at the laptop can reach the same app from their own
 * phone without typing an address, and it is hidden below `lg` — a judge already
 * holding the phone does not need a QR code to their own screen.
 *
 * SHAPE
 * A single compact CTA sits quietly under the scan flow. Clicking it opens a
 * centered modal that presents the QR code full-size ("Scan me"). The technical
 * detail lives inside the modal, not on the main screen.
 *
 * HONESTY RULES (both matter more than the convenience)
 *  - The target is derived from `window.location`, never from a hardcoded host,
 *    so the QR always encodes an address this browser is actually serving from.
 *  - When that address is loopback it is useless to another device, so NO QR is
 *    drawn at all; the modal explains what to change instead. A scannable code
 *    pointing at `localhost` would send the judge to their own phone.
 *
 * The plain text URL is always shown inside the modal, so it degrades to
 * something usable even if the code cannot be rendered.
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
  const [open, setOpen] = useState(false)

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
    <div className="hidden justify-center lg:flex">
      {/* Compact, intentional CTA — reads as an invitation, not a debug panel. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group inline-flex items-center gap-2.5 rounded-full border border-border bg-secondary/40 px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <Smartphone className="h-4 w-4 text-primary" aria-hidden />
        Try this on your phone
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <div className="flex flex-col items-center text-center">
            <div className="t-eyebrow">Exhibition</div>
            <DialogTitle className="mt-1.5 text-xl">
              {code ? "Scan me" : "Try this on your phone"}
            </DialogTitle>
            <DialogDescription className="mt-2 max-w-xs">
              The phone runs the same scan, the same policy decision and the same
              compliance check as this screen. Nothing is simulated for mobile.
            </DialogDescription>

            {code ? (
              <svg
                role="img"
                aria-label={`QR code for ${origin.target}`}
                viewBox={`0 0 ${code.size + 8} ${code.size + 8}`}
                className="mt-5 h-56 w-56 rounded-xl bg-white p-2.5 ring-1 ring-black/10"
                shapeRendering="crispEdges"
              >
                <path d={qrPath(code)} fill="#0f172a" />
              </svg>
            ) : (
              <span
                aria-hidden
                className="mt-5 flex h-56 w-56 items-center justify-center rounded-xl border border-dashed border-border bg-background"
              >
                <Smartphone className="h-12 w-12 text-muted-foreground/40" />
              </span>
            )}

            {/* Always shown: the code is a convenience, the address is the fallback. */}
            <p className="mt-5 w-full break-all rounded-lg bg-muted/60 px-3 py-2 font-mono text-sm font-semibold text-foreground">
              {origin.target}
            </p>

            {origin.loopback ? (
              <p className="t-meta mt-3">
                This page is being served from a loopback address, so the URL
                above only resolves on this laptop and no QR code is shown. Start
                the frontend on the network interface and reopen this page from
                the laptop&apos;s own LAN address to get a code another device can
                use — see the frontend README.
              </p>
            ) : (
              origin.insecure && (
                <p className="t-meta mt-3">
                  Phone browsers only grant camera access on a secure origin. If
                  the camera is blocked over plain HTTP, the phone can still use{" "}
                  <span className="font-semibold">Upload photo</span> and the flow
                  is identical.
                </p>
              )
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
