import Link from "next/link"
import { Navigation } from "./Navigation"
import { BackendStatus } from "./BackendStatus"
import { Recycle } from "lucide-react"

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="container flex h-16 items-center gap-4">
        <Link href="/scan" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-soft">
            <Recycle className="h-5 w-5" />
          </span>
          <span className="flex flex-col">
            <span className="font-bold leading-none tracking-tight text-foreground">MediWaste AI</span>
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
      {/* Mobile nav row — full width, evenly spread so it never overflows narrow screens. */}
      <div className="border-t border-border/70 md:hidden">
        <Navigation className="container justify-between py-1.5" />
      </div>
    </header>
  )
}
