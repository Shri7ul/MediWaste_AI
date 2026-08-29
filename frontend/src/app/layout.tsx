import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/Header";
import { NarrativeRail } from "@/components/layout/NarrativeRail";
import { StageProvider } from "@/components/layout/StageContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MediWaste AI | Intelligent Medical Waste Segregation & Compliance",
  description:
    "Intelligent medical waste segregation, compliance verification, and disposal operations.",
};

/**
 * Stated explicitly because the exhibition is judged on a phone. `maximumScale`
 * is deliberately NOT set — pinch-zoom stays available for accessibility.
 */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" style={{ colorScheme: "light" }}>
      <body
        className={`${inter.variable} font-sans min-h-screen bg-background text-foreground antialiased flex flex-col overflow-x-hidden`}
      >
        <StageProvider>
          <Header />
          <NarrativeRail />
          <main className="flex-1 container py-6 sm:py-8 md:py-10">{children}</main>
        </StageProvider>
      </body>
    </html>
  );
}
