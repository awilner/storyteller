import { useState, useEffect, useMemo } from "react";
import { fetchFile } from "./api";
import { useI18n } from "./I18nContext";
import MarkdownRenderer from "./MarkdownRenderer";
import "./FolderView.css";

function collectTexts(folder) {
  const result = [];
  const items = [];
  for (const child of folder.children || []) {
    items.push({ kind: "folder", data: child, order: child.order });
  }
  for (const text of folder.texts || []) {
    items.push({ kind: "text", data: text, order: text.order });
  }
  items.sort((a, b) => a.order - b.order);
  for (const item of items) {
    if (item.kind === "text") result.push(item.data);
    else result.push(...collectTexts(item.data));
  }
  return result;
}

export default function FolderView({ folder, onSelectFile, onCounts }) {
  const t = useI18n();
  const [texts, setTexts] = useState([]);
  const [contents, setContents] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!folder) return;
    const collected = collectTexts(folder);
    setTexts(collected);
    setContents({});
    if (collected.length === 0) return;
    setLoading(true);
    let cancelled = false;
    Promise.all(
      collected.map((tx) =>
        fetchFile(tx.id)
          .then((data) => ({ id: tx.id, content: data.content }))
          .catch(() => ({ id: tx.id, content: "" }))
      )
    ).then((results) => {
      if (cancelled) return;
      const map = {};
      for (const r of results) map[r.id] = r.content;
      setContents(map);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [folder?.id]);

  // Compute and report counts to parent
  const { wordCount, charCount } = useMemo(() => {
    let allText = "";
    for (const tx of texts) {
      const c = contents[tx.id];
      if (c) allText += (allText ? " " : "") + c;
    }
    const plain = allText.replace(/[#*_~`>\[\]()!|-]/g, "").trim();
    return {
      wordCount: plain ? plain.split(/\s+/).length : 0,
      charCount: plain.length,
    };
  }, [texts, contents]);

  useEffect(() => {
    if (onCounts) onCounts({ wordCount, charCount });
  }, [wordCount, charCount, onCounts]);

  if (!folder) return null;

  return (
    <div className="folder-view">
      <h2 className="folder-view-title">{folder.title}</h2>
      {loading && <p className="loading-text">{t("common.loading") || "Loading…"}</p>}
      {!loading && texts.length === 0 && (
        <p className="folder-empty">{t("editor.folder_empty") || "This folder has no texts."}</p>
      )}
      {!loading && texts.map((tx, i) => (
        <div key={tx.id}>
          {i > 0 && <hr className="folder-text-separator" />}
          <div className="folder-text-item" onClick={() => onSelectFile(tx.id)}>
            <h3 className="folder-text-heading">{tx.title}</h3>
            <MarkdownRenderer content={contents[tx.id] || ""} className="folder-text-content" />
          </div>
        </div>
      ))}
    </div>
  );
}
