import { useI18n } from "./I18nContext";

export default function NotesPage() {
  const t = useI18n();
  return (
    <div className="narrow-container">
      <h2>{t("nav.notes") || "Notes"}</h2>
      <p className="muted-text">The notes view will be available here in a future update.</p>
    </div>
  );
}
