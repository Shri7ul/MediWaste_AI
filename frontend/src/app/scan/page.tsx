import { ScanController } from "@/components/scan/ScanController"

export default function ScanPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="max-w-2xl">
        <div className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1 text-xs font-medium text-primary">
          Medical waste segregation &amp; compliance
        </div>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          MediWaste AI
        </h1>
        <p className="mt-2 text-base text-muted-foreground">
          AI-powered medical waste segregation and compliance. Capture an item to identify it,
          confirm the recommended bin, and verify disposal — every check is recorded for audit.
        </p>
      </header>

      <ScanController />
    </div>
  )
}
