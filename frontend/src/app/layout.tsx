import type { Metadata } from "next";
import { Ubuntu, Ubuntu_Mono, Oswald } from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

// Primary UI font — per enterprise-SKILL.md brand guidance.
const ubuntuSans = Ubuntu({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  display: "swap",
});

// Display/headline font — per enterprise-SKILL.md brand guidance.
const oswaldDisplay = Oswald({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

// Monospace (numerics in KPIs, run IDs, feature values).
const ubuntuMono = Ubuntu_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Karabük FWI — Wildfire Risk Prediction",
  description:
    "Operational wildfire risk prediction console for Karabük, Turkey — Stacked v3 (regression backbone + safety classifier)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${ubuntuSans.variable} ${oswaldDisplay.variable} ${ubuntuMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
