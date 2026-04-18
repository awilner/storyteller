import { useState, useEffect, useCallback, useRef } from "react";
import "./MetadataListManager.css";

/**
 * Reusable drag-and-drop list manager for labels and statuses.
 *
 * Props:
 *   projectId, embedded, onClose,
 *   title - heading text,
 *   addLabel - button text for "Add",
 *   defaultName - default name for new items,
 *   deleteWarningKey - i18n key for delete warning,
 *   fetchItems(projectId), createItem(projectId, data),
 *   updateItem(projectId, id, data), deleteItem(projectId, id, confirm),
 *   t - i18n function
 */
export default function MetadataListManager({
  projectId, embedded, onClose, title, addLabel, defaultName,
  deleteWarningKey, fetchItems, createItem, updateItem, deleteItem, t,
  readOnly,
}) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [insertBefore, setInsertBefore] = useState(null);
  const listRef = useRef(null);
  const insertRef = useRef(null);

  useEffect(() => { insertRef.current = insertBefore; }, [insertBefore]);

  const load = useCallback(async () => {
    try { setItems(await fetchItems(projectId)); } catch (err) { setError(err.message); }
  }, [projectId, fetchItems]);
  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    try {
      await createItem(projectId, { name: defaultName, colour: "#888888", order: items.length });
      await load();
    } catch (err) { setError(err.message); }
  };

  const handleUpdate = async (id, data) => {
    try { await updateItem(projectId, id, data); await load(); } catch (err) { setError(err.message); }
  };

  const handleDelete = async (id, name) => {
    try {
      const result = await deleteItem(projectId, id, false);
      if (result && result.count) {
        if (!window.confirm(t(deleteWarningKey, { name, count: String(result.count) }))) return;
        await deleteItem(projectId, id, true);
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
      let target = rows.length;
      for (const row of rows) {
        const rect = row.getBoundingClientRect();
        if (ev.clientY < rect.top + rect.height / 2) { target = Number(row.dataset.rowIndex); break; }
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
      const actualTo = to > fromIndex ? to - 1 : to;
      setItems((prev) => {
        const reordered = [...prev];
        const [moved] = reordered.splice(fromIndex, 1);
        reordered.splice(actualTo, 0, moved);
        (async () => {
          try {
            for (let i = 0; i < reordered.length; i++) {
              if (reordered[i].order !== i) await updateItem(projectId, reordered[i].id, { order: i });
            }
          } catch { /* ignore */ }
        })();
        return reordered;
      });
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }, [projectId, updateItem]);

  const content = (
    <>
      <div className="mdlist-items" ref={listRef}>
        {items.map((item, i) => (
          <div key={item.id} data-row-index={i}
            className={`mdlist-row${dragging === i ? " mdlist-row--dragging" : ""}${insertBefore === i && dragging !== null && dragging !== i ? " mdlist-row--insert-before" : ""}`}>
            {!readOnly && <span className="mdlist-grip" onPointerDown={(e) => handleGripDown(e, i)}>⠿</span>}
            <input type="color" className="mdlist-colour" value={item.colour || "#000000"}
              disabled={readOnly}
              onChange={(e) => setItems((prev) => prev.map((x) => x.id === item.id ? { ...x, colour: e.target.value } : x))}
              onBlur={(e) => handleUpdate(item.id, { colour: e.target.value })} />
            <input className="mdlist-name" value={item.name}
              disabled={readOnly}
              onChange={(e) => setItems((prev) => prev.map((x) => x.id === item.id ? { ...x, name: e.target.value } : x))}
              onBlur={(e) => handleUpdate(item.id, { name: e.target.value })} />
            {!readOnly && <button type="button" className="mdlist-btn mdlist-btn--danger" onClick={() => handleDelete(item.id, item.name)} aria-label="Delete">✕</button>}
          </div>
        ))}
        {dragging !== null && insertBefore === items.length && <div className="mdlist-insert-line" />}
      </div>
      {error && <div className="mdlist-error">{error}</div>}
      {!readOnly && (
        <div style={{ paddingTop: 8 }}>
          <button type="button" className="mdlist-btn" onClick={handleAdd}>{addLabel}</button>
        </div>
      )}
    </>
  );

  if (embedded) return content;
  return (
    <div className="mdlist-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="mdlist-modal"><h3>{title}</h3>{content}
        <div className="mdlist-footer"><button type="button" className="mdlist-btn" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}
