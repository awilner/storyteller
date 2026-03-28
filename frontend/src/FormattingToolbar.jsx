import { useState, useEffect } from "react";
import { useI18n } from "./I18nContext";

const Icon = ({ d, size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

// Filled icon variant (for list dots, etc.)
const FilledIcon = ({ children, size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

const icons = {
  bold: (
    <FilledIcon>
      <path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z" />
      <path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z" />
    </FilledIcon>
  ),
  italic: <Icon d="M19 4h-9M14 20H5M15 4L9 20" />,
  blockquote: (
    <FilledIcon>
      <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z" />
      <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z" />
    </FilledIcon>
  ),
  h1: (
    <FilledIcon>
      <path d="M4 12h8" /><path d="M4 18V6" /><path d="M12 18V6" />
      <path d="M17 12l3-2v8" />
    </FilledIcon>
  ),
  h2: (
    <FilledIcon>
      <path d="M4 12h8" /><path d="M4 18V6" /><path d="M12 18V6" />
      <path d="M21 18h-4c0-4 4-3 4-6 0-1.5-2-2.5-4-1" />
    </FilledIcon>
  ),
  h3: (
    <FilledIcon>
      <path d="M4 12h8" /><path d="M4 18V6" /><path d="M12 18V6" />
      <path d="M17.5 10.5c1.7-1 3.5 0 3.5 1.5a2 2 0 0 1-2 2" />
      <path d="M17 17.5c2 1.5 4 .3 4-1.5a2 2 0 0 0-2-2" />
    </FilledIcon>
  ),
  bulletList: (
    <FilledIcon>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <circle cx="4" cy="6" r="1" fill="currentColor" />
      <circle cx="4" cy="12" r="1" fill="currentColor" />
      <circle cx="4" cy="18" r="1" fill="currentColor" />
    </FilledIcon>
  ),
  orderedList: (
    <FilledIcon>
      <line x1="10" y1="6" x2="21" y2="6" />
      <line x1="10" y1="12" x2="21" y2="12" />
      <line x1="10" y1="18" x2="21" y2="18" />
      <path d="M4 6h1v4" /><path d="M4 10h2" />
      <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
    </FilledIcon>
  ),
  code: (
    <FilledIcon>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </FilledIcon>
  ),
  link: (
    <FilledIcon>
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </FilledIcon>
  ),
};

export default function FormattingToolbar({ editor }) {
  const t = useI18n();
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!editor) return;
    const onTransaction = () => setTick((t) => t + 1);
    editor.on("transaction", onTransaction);
    return () => editor.off("transaction", onTransaction);
  }, [editor]);

  if (!editor || editor.isDestroyed) return null;

  const btnStyle = (active) => ({
    padding: "4px 6px",
    border: "1px solid " + (active ? "#333" : "#ccc"),
    borderRadius: 4,
    cursor: "pointer",
    background: active ? "#333" : "#f5f5f5",
    color: active ? "#fff" : "#333",
    fontSize: 13,
    lineHeight: 1,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minWidth: 28,
    height: 28,
  });

  const handleLink = () => {
    const url = window.prompt(t("toolbar.enter_url"));
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    } else {
      editor.chain().focus().unsetLink().run();
    }
  };

  const buttons = [
    { key: "bold", icon: icons.bold, label: t("toolbar.bold"), active: editor.isActive("bold"), action: () => editor.chain().focus().toggleBold().run() },
    { key: "italic", icon: icons.italic, label: t("toolbar.italic"), active: editor.isActive("italic"), action: () => editor.chain().focus().toggleItalic().run() },
    { key: "blockquote", icon: icons.blockquote, label: t("toolbar.blockquote"), active: editor.isActive("blockquote"), action: () => editor.chain().focus().toggleBlockquote().run() },
    { key: "h1", icon: icons.h1, label: t("toolbar.heading1"), active: editor.isActive("heading", { level: 1 }), action: () => editor.chain().focus().toggleHeading({ level: 1 }).run() },
    { key: "h2", icon: icons.h2, label: t("toolbar.heading2"), active: editor.isActive("heading", { level: 2 }), action: () => editor.chain().focus().toggleHeading({ level: 2 }).run() },
    { key: "h3", icon: icons.h3, label: t("toolbar.heading3"), active: editor.isActive("heading", { level: 3 }), action: () => editor.chain().focus().toggleHeading({ level: 3 }).run() },
    { key: "bullet", icon: icons.bulletList, label: t("toolbar.bullet_list"), active: editor.isActive("bulletList"), action: () => editor.chain().focus().toggleBulletList().run() },
    { key: "ordered", icon: icons.orderedList, label: t("toolbar.ordered_list"), active: editor.isActive("orderedList"), action: () => editor.chain().focus().toggleOrderedList().run() },
    { key: "code", icon: icons.code, label: t("toolbar.code"), active: editor.isActive("code"), action: () => editor.chain().focus().toggleCode().run() },
    { key: "link", icon: icons.link, label: t("toolbar.link"), active: editor.isActive("link"), action: handleLink },
  ];

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3, padding: "6px 0" }}>
      {buttons.map((btn) => (
        <button
          key={btn.key}
          type="button"
          style={btnStyle(btn.active)}
          onClick={btn.action}
          title={btn.label}
          aria-label={btn.label}
        >
          {btn.icon}
        </button>
      ))}
    </div>
  );
}
