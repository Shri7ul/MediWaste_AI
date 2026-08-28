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
            "rounded-md px-2.5 py-2 text-sm font-medium transition-colors hover:text-primary lg:px-3",
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
