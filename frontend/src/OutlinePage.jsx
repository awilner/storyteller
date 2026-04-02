import { useI18n } from "./I18nContext";

export default function OutlinePage() {
  const t = useI18n();
  return (
    <div className="narrow-container">
      <h2>{t("nav.outline") || "Outline"}</h2>
      <p className="muted-text">The outline view will be available here in a future update.</p>
    </div>
  );
}
