import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/Header";

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" style={{ colorScheme: "light" }}>
      <body
        className={`${inter.variable} font-sans min-h-screen bg-background text-foreground antialiased flex flex-col`}
      >
        <Header />
        <main className="flex-1 container py-8 md:py-10">{children}</main>
      </body>
    </html>
  );
}
