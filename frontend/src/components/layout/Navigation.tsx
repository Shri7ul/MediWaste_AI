"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

export function Navigation({ className }: { className?: string }) {
  const pathname = usePathname()

  const links = [
    { href: "/scan", label: "Analyze" },
    { href: "/operations", label: "Operations" },
    { href: "/dashboard", label: "Dashboard" },
    { href: "/events", label: "Events" },
  ]

  return (
    <nav className={cn("flex items-center", className)}>
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={pathname.startsWith(link.href) ? "page" : undefined}
          className={cn(
            // shrink-0 + whitespace-nowrap: in the mobile scroll row the labels
            // must never compress or wrap. min-h-[44px] keeps the tap target
            // comfortable on a phone without adding height on desktop.
            "inline-flex shrink-0 items-center whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[44px] md:min-h-0 lg:px-3",
            pathname.startsWith(link.href)
              ? "bg-secondary text-primary"
              : "text-muted-foreground"
          )}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  )
}
