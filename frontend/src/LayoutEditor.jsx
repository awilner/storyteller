export const DEFAULT_LAYOUT_SETTINGS = {
  chapter_heading_style: "title",
  page_break_before_chapter: true,
  blank_page_before_chapter: false,
  body_font_family: "Times New Roman",
  body_font_size: 12,
  heading_font_family: "Times New Roman",
  heading_font_size: 18,
  show_scene_titles: false,
  scene_separator: "three_asterisks",
  scene_separator_custom_text: "",
  margin_top: "2.54cm",
  margin_bottom: "2.54cm",
  margin_left: "3.18cm",
  margin_right: "3.18cm",
};

const FONT_OPTIONS = [
  "Times New Roman", "Georgia", "Garamond", "Palatino", "Book Antiqua",
  "Arial", "Helvetica", "Verdana", "Trebuchet MS", "Calibri",
  "Courier New", "Consolas", "Monaco",
  "Baskerville", "Cambria", "Century Schoolbook",
];

function FontSelect({ value, onChange }) {
  return (
    <select value={value} onChange={onChange} style={{ flex: 1, padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13 }}>
      {FONT_OPTIONS.map((f) => (
        <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>
      ))}
    </select>
  );
}

export default function LayoutEditor({ settings, onChange, t }) {
  const s = { ...DEFAULT_LAYOUT_SETTINGS, ...settings };
  const change = (key, value) => onChange(key, value);

  return (
    <div className="compile-layout-editor">
      <div className="compile-layout-field">
        <label>{t("compile.heading_style")}</label>
        <select value={s.chapter_heading_style} onChange={(e) => change("chapter_heading_style", e.target.value)}>
          <option value="title">{t("compile.heading_title")}</option>
          <option value="numbered">{t("compile.heading_numbered")}</option>
          <option value="numbered_title">{t("compile.heading_numbered_title")}</option>
        </select>
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.page_break")}</label>
        <input type="checkbox" checked={s.page_break_before_chapter} onChange={(e) => change("page_break_before_chapter", e.target.checked)} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.blank_page")}</label>
        <input type="checkbox" checked={s.blank_page_before_chapter} onChange={(e) => change("blank_page_before_chapter", e.target.checked)} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.body_font")}</label>
        <FontSelect value={s.body_font_family} onChange={(e) => change("body_font_family", e.target.value)} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.body_font_size")}</label>
        <input type="number" value={s.body_font_size} min={6} max={72} onChange={(e) => change("body_font_size", Number(e.target.value))} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.heading_font")}</label>
        <FontSelect value={s.heading_font_family} onChange={(e) => change("heading_font_family", e.target.value)} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.heading_font_size")}</label>
        <input type="number" value={s.heading_font_size} min={6} max={72} onChange={(e) => change("heading_font_size", Number(e.target.value))} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.show_scene_titles")}</label>
        <input type="checkbox" checked={s.show_scene_titles} onChange={(e) => change("show_scene_titles", e.target.checked)} />
      </div>
      <div className="compile-layout-field">
        <label>{t("compile.scene_separator")}</label>
        <select value={s.scene_separator} onChange={(e) => change("scene_separator", e.target.value)}>
          <option value="horizontal_rule">{t("compile.separator_horizontal_rule")}</option>
          <option value="three_asterisks">{t("compile.separator_three_asterisks")}</option>
          <option value="custom_text">{t("compile.separator_custom_text")}</option>
          <option value="blank_line">{t("compile.separator_blank_line")}</option>
          <option value="none">{t("compile.separator_none")}</option>
        </select>
      </div>
      {s.scene_separator === "custom_text" && (
        <div className="compile-layout-field">
          <label>{t("compile.custom_separator_text")}</label>
          <input type="text" value={s.scene_separator_custom_text} onChange={(e) => change("scene_separator_custom_text", e.target.value)} />
        </div>
      )}
      <div>
        <span className="compile-section-label">{t("compile.margins")}</span>
        <div className="compile-margins-grid">
          <div><label>{t("compile.margin_top")}</label><input type="text" value={s.margin_top} onChange={(e) => change("margin_top", e.target.value)} /></div>
          <div><label>{t("compile.margin_bottom")}</label><input type="text" value={s.margin_bottom} onChange={(e) => change("margin_bottom", e.target.value)} /></div>
          <div><label>{t("compile.margin_left")}</label><input type="text" value={s.margin_left} onChange={(e) => change("margin_left", e.target.value)} /></div>
          <div><label>{t("compile.margin_right")}</label><input type="text" value={s.margin_right} onChange={(e) => change("margin_right", e.target.value)} /></div>
        </div>
      </div>
    </div>
  );
}
