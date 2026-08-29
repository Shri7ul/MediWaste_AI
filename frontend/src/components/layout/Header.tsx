import Link from "next/link"
import { Navigation } from "./Navigation"
import { BackendStatus } from "./BackendStatus"
import { Recycle } from "lucide-react"

/**
 * Application header.
 *
 * Phone behaviour (deliberate):
 *  - It is NOT sticky below `md`. A permanently pinned bar plus the narrative
 *    rail costs ~90px of a 640px-tall viewport, and on /scan that height belongs
 *    to the camera. From `md` up it pins as before.
 *  - Priority order on a narrow screen is identity → backend status → minimal
 *    navigation. The nav row scrolls horizontally instead of wrapping, so the
 *    four destinations stay reachable without ever overflowing the page.
 */
export function Header() {
  return (
    <header className="top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70 md:sticky">
      <div className="container flex h-14 items-center gap-3 md:h-16 md:gap-4">
        <Link href="/scan" className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-soft">
            <Recycle className="h-5 w-5" />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-bold leading-none tracking-tight text-foreground">MediWaste AI</span>
            <span className="mt-1 hidden text-[11px] text-muted-foreground sm:block">
              Intelligent Medical Waste Segregation &amp; Compliance
            </span>
          </span>
        </Link>
        <div className="flex flex-1 items-center justify-end gap-3 md:gap-6">
          {/* Desktop: inline nav. On mobile the nav drops to its own full-width row below. */}
          <Navigation className="hidden gap-1 md:flex lg:gap-3" />
          <BackendStatus />
        </div>
      </div>
      {/* Mobile nav row — scrolls sideways rather than wrapping or squeezing. */}
      <div className="border-t border-border/70 md:hidden">
        <Navigation className="container gap-1 overflow-x-auto" />
      </div>
    </header>
  )
}
