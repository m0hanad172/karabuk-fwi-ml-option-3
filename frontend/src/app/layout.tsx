import type { Metadata } from "next";

import { Providers } from "@/components/providers";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Karabuk FWI - Wildfire Risk Prediction",
  description:
    "Operational wildfire risk prediction console for Karabuk, Turkey - Stacked v3 (regression backbone + safety classifier)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
