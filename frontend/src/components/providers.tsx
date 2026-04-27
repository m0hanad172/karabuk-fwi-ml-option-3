"use client";

import type { ReactNode } from "react";

import { LanguageProvider } from "@/lib/i18n-context";

/**
 * Single client-side provider wrapper mounted at the root layout. Keeps
 * `app/layout.tsx` server-rendered while providing the language context
 * to every client component beneath it.
 */
export function Providers({ children }: { children: ReactNode }) {
  return <LanguageProvider>{children}</LanguageProvider>;
}
