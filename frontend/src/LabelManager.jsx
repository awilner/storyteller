import { useState, useEffect, useCallback, useRef } from "react";
import { useI18n } from "./I18nContext";
import { fetchLabels, createLabel, updateLabel, deleteLabel } from "./api";
import "./LabelManager.css";

export default function LabelManager({ projectId, onClose, embedded }) {
  const t = useI18n();
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [insertBefore, setInsertBefore] = useState(null); // index where the line shows
  const listRef = useRef(null);
  const insertRef = useRef(null);

  useEffect(() => { insertRef.current = insertBefore; }, [insertBefore]);

  const load = useCallback(async () => {
    try { setItems(await fetchLabels(projectId)); } catch (err) { setError(err.message); }
  }, [projectId]);
  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    try {
      await createLabel(projectId, { name: t("labels.name"), colour: "#888888", order: items.length });
      await load();
    } catch (err) { setError(err.message); }
  };

  const handleUpdate = async (id, data) => {
    try { await updateLabel(projectId, id, data); await load(); } catch (err) { setError(err.message); }
  };

  const handleDelete = async (id, name) => {
    try {
      const result = await deleteLabel(projectId, id, false);
      if (result && result.count) {
        if (!window.confirm(t("labels.delete_warning", { name, count: String(result.count) }))) return;
        await deleteLabel(projectId, id, true);
      }
      await load();
    } catch (err) { setError(err.message); }
  };

  const handleGripDown = useCallback((e, fromIndex) => {
    e.preventDefault();
    setDragging(fromIndex);
    setInsertBefore(fromIndex);

    const onMove = (ev) => {
      if (!listRef.current) return;
      const rows = listRef.current.querySelectorAll("[data-row-index]");
      // Find insertion point: the gap between rows closest to the cursor
      let target = rows.length; // default: after last
      for (const row of rows) {
        const rect = row.getBoundingClientRect();
        if (ev.clientY < rect.top + rect.height / 2) {
          target = Number(row.dataset.rowIndex);
          break;
        }
      }
      setInsertBefore(target);
    };

    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      const to = insertRef.current;
      setDragging(null);
      setInsertBefore(null);
      if (to === null || to === fromIndex || to === fromIndex + 1) return;
      // Compute the actual target after removal
      const actualTo = to > fromIndex ? to - 1 : to;

      setItems((prev) => {
        const reordered = [...prev];
        const [moved] = reordered.splice(fromIndex, 1);
        reordered.splice(actualTo, 0, moved);
        (async () => {
          try {
            for (let i = 0; i < reordered.length; i++) {
              if (reordered[i].order !== i) await updateLabel(projectId, reordered[i].id, { order: i });
            }
          } catch { /* ignore */ }
        })();
        return reordered;
      });
    };

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }, [projectId]);

  const content = (
    <>
      <div className="label-manager-list" ref={listRef}>
        {items.map((item, i) => (
          <div key={item.id} data-row-index={i}
            className={`label-manager-row${dragging === i ? " label-manager-row--dragging" : ""}${insertBefore === i && dragging !== null && dragging !== i ? " label-manager-row--insert-before" : ""}`}>
            <span className="label-manager-grip" onPointerDown={(e) => handleGripDown(e, i)}>⠿</span>
            <input type="color" className="label-manager-colour" value={item.colour || "#000000"}
              onChange={(e) => { setItems((prev) => prev.map((x) => x.id === item.id ? { ...x, colour: e.target.value } : x)); }}
              onBlur={(e) => handleUpdate(item.id, { colour: e.target.value })} />
            <input className="label-manager-name" value={item.name}
              onChange={(e) => setItems((prev) => prev.map((x) => x.id === item.id ? { ...x, name: e.target.value } : x))}
              onBlur={(e) => handleUpdate(item.id, { name: e.target.value })} />
            <button type="button" className="label-manager-btn label-manager-btn--danger" onClick={() => handleDelete(item.id, item.name)} aria-label="Delete">✕</button>
          </div>
        ))}
        {/* Show insert line after last item when dragging to the end */}
        {dragging !== null && insertBefore === items.length && (
          <div className="label-manager-insert-line" />
        )}
      </div>
      {error && <div className="label-manager-error">{error}</div>}
      <div style={{ paddingTop: 8 }}>
        <button type="button" className="label-manager-btn" onClick={handleAdd}>{t("labels.add")}</button>
      </div>
    </>
  );

  if (embedded) return content;
  return (
    <div className="label-manager-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="label-manager-modal"><h3>{t("labels.title")}</h3>{content}
        <div className="label-manager-footer"><button type="button" className="label-manager-btn" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}
