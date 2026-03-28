import { createContext, useContext, useState, useEffect } from "react";
import { fetchTranslations } from "./api";

const I18nContext = createContext({});

export function I18nProvider({ children }) {
  const [strings, setStrings] = useState(null);

  useEffect(() => {
    fetchTranslations()
      .then(setStrings)
      .catch(() => setStrings({}));
  }, []);

  // Don't render children until translations are loaded
  if (strings === null) return null;

  return (
    <I18nContext.Provider value={strings}>
      {children}
    </I18nContext.Provider>
  );
}

/**
 * Hook to access translated strings.
 * Usage: const t = useI18n(); t("auth.login")
 * Supports interpolation: t("key", { title: "foo" })
 */
export function useI18n() {
  const strings = useContext(I18nContext);
  return (key, params) => {
    let val = strings[key] || key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        val = val.replace(`%(${k})s`, v);
      }
    }
    return val;
  };
}
