import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";

import {
  applyDocumentTranslations,
  translateText,
  TRANSLATABLE_ATTRIBUTES,
  type AppLocale,
} from "@/lib/i18n";
import { useUIStore } from "@/store/uiStore";

interface I18nContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  toggleLocale: () => void;
  t: (value: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const locale = useUIStore((state) => state.locale);
  const setLocale = useUIStore((state) => state.setLocale);
  const toggleLocale = useUIStore((state) => state.toggleLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dataset.locale = locale;
    applyDocumentTranslations(document.body, locale);

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "childList") {
          mutation.addedNodes.forEach((node) => {
            if (node instanceof Element) {
              applyDocumentTranslations(node, locale);
            } else if (node instanceof Text && node.parentElement) {
              applyDocumentTranslations(node.parentElement, locale);
            }
          });
        }

        if (mutation.type === "characterData" && mutation.target.parentElement) {
          applyDocumentTranslations(mutation.target.parentElement, locale);
        }

        if (mutation.type === "attributes" && mutation.target instanceof Element) {
          applyDocumentTranslations(mutation.target, locale);
        }
      }
    });

    observer.observe(document.body, {
      attributeFilter: [...TRANSLATABLE_ATTRIBUTES],
      attributes: true,
      characterData: true,
      childList: true,
      subtree: true,
    });

    return () => observer.disconnect();
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale,
      toggleLocale,
      t: (text: string) => translateText(text, locale),
    }),
    [locale, setLocale, toggleLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
