import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { fetchUserSettings, updateUserSettings } from "./api";

const FontContext = createContext({
  userFont: "",
  projectFont: "",
  effectiveFont: "system-ui",
  setUserFont: () => {},
  setProjectFont: () => {},
});

const FONT_OPTIONS = [
  { value: "", label: "System Default" },
  { value: "Georgia, serif", label: "Georgia" },
  { value: "'Times New Roman', serif", label: "Times New Roman" },
  { value: "'Palatino Linotype', Palatino, serif", label: "Palatino" },
  { value: "'Libre Baskerville', serif", label: "Libre Baskerville" },
  { value: "'Merriweather', serif", label: "Merriweather" },
  { value: "system-ui, sans-serif", label: "System UI" },
  { value: "'Courier New', monospace", label: "Courier New" },
];

export { FONT_OPTIONS };

export function FontProvider({ children }) {
  const [userFont, setUserFontState] = useState("");
  const [projectFont, setProjectFont] = useState("");

  // Load user font preference on mount
  useEffect(() => {
    fetchUserSettings()
      .then((prefs) => { if (prefs.default_editor_font) setUserFontState(prefs.default_editor_font); })
      .catch(() => {});
  }, []);

  const setUserFont = useCallback((font) => {
    setUserFontState(font);
    updateUserSettings({ default_editor_font: font }).catch(() => {});
  }, []);

  // Project font overrides user font; fall back to system-ui
  const effectiveFont = projectFont || userFont || "system-ui";

  // Apply as CSS variable on document root
  useEffect(() => {
    document.documentElement.style.setProperty("--editor-font", effectiveFont);
  }, [effectiveFont]);

  return (
    <FontContext.Provider value={{ userFont, projectFont, effectiveFont, setUserFont, setProjectFont }}>
      {children}
    </FontContext.Provider>
  );
}

export function useFont() {
  return useContext(FontContext);
}
