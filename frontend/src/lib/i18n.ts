/**
 * Lightweight i18n dictionary + types.
 *
 * Design:
 *   - English is the default and primary language.
 *   - Turkish is offered as a second language via a top-bar switcher.
 *   - Only ONE language is rendered at a time — no simultaneous display.
 *   - The selected language is persisted in localStorage (see
 *     `i18n-context.tsx`).
 *
 * This file is server-safe (no React imports). The client-side provider,
 * hooks, and persistence logic live in `i18n-context.tsx`.
 */

export type Lang = "en" | "tr";

export const LANGS: readonly Lang[] = ["en", "tr"] as const;
export const DEFAULT_LANG: Lang = "en";

export interface Dict {
  brand: { name: string; tagline: string };
  groups: { Main: string; Operations: string; System: string };
  topbar: {
    consoleEyebrow: string;
    karabukChip: string;
    istanbulChip: string;
    openMenu: string;
  };
  footer: { productLine: string; scope: string };
  scope: { primary: string };
  sidebar: {
    scopeLabel: string;
    scopeLocation: string;
    scopeTimezone: string;
  };
  switcher: {
    ariaLabel: string;
    en: string;
    tr: string;
    enFull: string;
    trFull: string;
  };
  nav: Record<
    | "overview"
    | "impact"
    | "risk"
    | "features"
    | "analytics"
    | "history"
    | "monitoring"
    | "alerts"
    | "system"
    | "flow",
    { label: string; sub: string }
  >;
}

export const DICT: Record<Lang, Dict> = {
  en: {
    brand: {
      name: "Karabük FWI",
      tagline: "Wildfire Risk Console",
    },
    groups: {
      Main: "Main",
      Operations: "Operations",
      System: "System",
    },
    topbar: {
      consoleEyebrow: "Operational Console",
      karabukChip: "Karabük, Turkey",
      istanbulChip: "Istanbul (TRT)",
      openMenu: "Open navigation menu",
    },
    footer: {
      productLine:
        "Karabük FWI ML v2.0 — Stacked v3 (regression backbone + safety classifier)",
      scope: "All times Europe/Istanbul (TRT)",
    },
    scope: {
      primary: "Primary navigation",
    },
    sidebar: {
      scopeLabel: "Scope",
      scopeLocation: "Karabük, Turkey",
      scopeTimezone: "Timezone: Europe/Istanbul (TRT)",
    },
    switcher: {
      ariaLabel: "Select interface language",
      en: "EN",
      tr: "TR",
      enFull: "English",
      trFull: "Türkçe",
    },
    nav: {
      overview: {
        label: "Overview",
        sub: "Executive operational summary for Karabük fire risk.",
      },
      impact: {
        label: "Impact & Context",
        sub: "Why this system matters — 2025 Karabük wildfire impact and motivation.",
      },
      risk: {
        label: "Risk Decision",
        sub: "Stage 1 regression, Stage 2 safety classifier, final decision.",
      },
      features: {
        label: "Features",
        sub: "Raw inputs and engineered features used by the latest run.",
      },
      analytics: {
        label: "Analytics",
        sub: "Historical FWI trends, yearly and seasonal comparisons.",
      },
      history: {
        label: "Run History",
        sub: "Audit trail of manual and scheduled operational runs.",
      },
      monitoring: {
        label: "Monitoring",
        sub: "Drone, webcam and PC camera feeds with fire-detection alerts.",
      },
      alerts: {
        label: "Detection Alerts",
        sub: "Durable evidence log of fire detections — drone, webcam and PC camera.",
      },
      system: {
        label: "System / Model",
        sub: "Model version, thresholds, scheduler and data-quality health.",
      },
      flow: {
        label: "System Flow",
        sub: "End-to-end walkthrough — data fetch → features → Stage 1/2 → decision → audit.",
      },
    },
  },
  tr: {
    brand: {
      name: "Karabük FWI",
      tagline: "Yangın Riski Konsolu",
    },
    groups: {
      Main: "Ana",
      Operations: "Operasyon",
      System: "Sistem",
    },
    topbar: {
      consoleEyebrow: "Operasyonel Konsol",
      karabukChip: "Karabük, Türkiye",
      istanbulChip: "İstanbul (TRT)",
      openMenu: "Menüyü aç",
    },
    footer: {
      productLine:
        "Karabük FWI ML v2.0 — Stacked v3 (regresyon omurgası + güvenlik sınıflandırıcı)",
      scope: "Tüm saatler Europe/Istanbul (TRT)",
    },
    scope: {
      primary: "Birincil gezinme",
    },
    sidebar: {
      scopeLabel: "Kapsam",
      scopeLocation: "Karabük, Türkiye",
      scopeTimezone: "Saat dilimi: Europe/Istanbul (TRT)",
    },
    switcher: {
      ariaLabel: "Arayüz dilini seçin",
      en: "EN",
      tr: "TR",
      enFull: "English",
      trFull: "Türkçe",
    },
    nav: {
      overview: {
        label: "Genel Bakış",
        sub: "Karabük yangın riski operasyonel özeti.",
      },
      impact: {
        label: "Etki ve Bağlam",
        sub: "Sistem neden var — 2025 Karabük yangını etkisi ve motivasyonu.",
      },
      risk: {
        label: "Risk Kararı",
        sub: "Aşama 1 regresyon, Aşama 2 güvenlik sınıflandırıcısı ve nihai karar.",
      },
      features: {
        label: "Özellikler",
        sub: "Son operasyonel çalıştırmada kullanılan ham ve türetilmiş özellikler.",
      },
      analytics: {
        label: "Analitik",
        sub: "Tarihsel FWI eğilimleri; yıllık ve mevsimsel karşılaştırmalar.",
      },
      history: {
        label: "Çalıştırma Geçmişi",
        sub: "Manuel ve zamanlanmış operasyonel çalıştırmaların denetim izi.",
      },
      monitoring: {
        label: "İzleme",
        sub: "Drone, webcam ve dizüstü kamerası ile yangın tespiti.",
      },
      alerts: {
        label: "Tespit Uyarıları",
        sub: "Drone ve kamera tespitlerinin dayanıklı kanıt günlüğü.",
      },
      system: {
        label: "Sistem / Model",
        sub: "Model sürümü, eşikler, zamanlayıcı ve veri kalitesi.",
      },
      flow: {
        label: "Sistem Akışı",
        sub: "Uçtan uca anlatım — veri çekme → özellikler → Aşama 1/2 → karar → denetim.",
      },
    },
  },
};
