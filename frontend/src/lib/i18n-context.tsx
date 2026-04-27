"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { DEFAULT_LANG, DICT, type Dict, type Lang } from "./i18n";

const STORAGE_KEY = "karabuk-fwi.lang";

interface LanguageContextValue {
  lang: Lang;
  setLang: (next: Lang) => void;
  t: Dict;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function isLang(value: unknown): value is Lang {
  return value === "en" || value === "tr";
}

/**
 * Client-side language provider.
 *
 * - Default language is English (so first paint matches what unlocalised
 *   users expect and SSR stays deterministic).
 * - On mount we read `localStorage` and upgrade to the user's stored
 *   choice. The initial flash is unavoidable for a client-only store but
 *   negligible for a primarily-English product surface.
 * - `setLang` writes through to localStorage and updates `<html lang>`
 *   so assistive tech and browser spellcheck switch with the UI.
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (isLang(stored)) setLangState(stored);
    } catch {
      // localStorage can throw in private mode — safe to ignore.
    }
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = lang;
    }
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo<LanguageContextValue>(
    () => ({ lang, setLang, t: DICT[lang] }),
    [lang, setLang],
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

function useLanguageContext(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguageContext must be used inside <LanguageProvider>");
  }
  return ctx;
}

export function useLang(): Lang {
  return useLanguageContext().lang;
}

export function useSetLang(): (next: Lang) => void {
  return useLanguageContext().setLang;
}

export function useT(): Dict {
  return useLanguageContext().t;
}
