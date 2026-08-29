import { ScanController } from "@/components/scan/ScanController"
import { PhoneHandoff } from "@/components/exhibition/PhoneHandoff"

export default function ScanPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 sm:space-y-8">
      {/* Hero — the entrance to the product. Three short lines, no marketing
          paragraph: who this is, what it does, and what the operator is about to
          do. Nothing about the internals belongs on this screen. */}
      <header className="max-w-2xl">
        <div className="t-eyebrow">MediWaste AI</div>
        <h1 className="t-hero mt-1.5 text-[27px] sm:text-4xl">
          Intelligent Medical Waste Segregation
        </h1>
        <p className="mt-2 text-base font-medium text-muted-foreground">
          Identify the waste. Apply the policy. Verify the disposal route.
        </p>
      </header>

      <ScanController />

      {/* Exhibition convenience only, and only on a large screen — a judge already
          holding a phone does not need a QR code to their own screen. */}
      <PhoneHandoff />
    </div>
  )
}
