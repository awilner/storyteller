import { useEffect, useRef, useMemo, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Markdown } from "tiptap-markdown";
import Collaboration from "@tiptap/extension-collaboration";
import CollaborationCursor from "@tiptap/extension-collaboration-cursor";
import { HocuspocusProvider } from "@hocuspocus/provider";
import * as Y from "yjs";
import "./TipTapEditor.css";

/**
 * Build the WebSocket URL for the HocusPocus provider.
 * In production, nginx proxies /yjs/ to HocusPocus.
 * In dev, Vite proxies /yjs to ws://localhost:1234.
 */
function getHocuspocusUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/yjs`;
}

/**
 * Probe whether the HocusPocus server is reachable.
 * Resolves to true if a WebSocket connection opens, false on error/timeout.
 */
function probeHocuspocusServer(timeoutMs = 2000) {
  return new Promise((resolve) => {
    try {
      const wsUrl = getHocuspocusUrl();
      const ws = new WebSocket(wsUrl);
      const timer = setTimeout(() => { ws.close(); resolve(false); }, timeoutMs);
      ws.onopen = () => { clearTimeout(timer); ws.close(); resolve(true); };
      ws.onerror = () => { clearTimeout(timer); ws.close(); resolve(false); };
    } catch {
      resolve(false);
    }
  });
}

export default function TipTapEditor({
  content,
  onUpdate,
  editorRef,
  isCollaborative = false,
  fileId,
  username,
  userColor,
  permission,
  onCollabStatusChange,
}) {
  const ydocRef = useRef(null);
  const providerRef = useRef(null);
  const prevFileIdRef = useRef(null);

  // Start in REST mode; only activate collab after a successful probe.
  const [collabReady, setCollabReady] = useState(false);

  // Probe the HocusPocus server once when collaborative mode is requested.
  // Cache the result for the session so subsequent file switches are instant.
  const probeResultRef = useRef(null); // null = not probed, true/false = result

  useEffect(() => {
    if (!isCollaborative) {
      setCollabReady(false);
      onCollabStatusChange?.("online");
      return;
    }

    let cancelled = false;

    if (probeResultRef.current === true) {
      setCollabReady(true);
      onCollabStatusChange?.("online");
      return;
    }
    if (probeResultRef.current === false) {
      setCollabReady(false);
      onCollabStatusChange?.("offline");
      return;
    }

    probeHocuspocusServer().then((ok) => {
      if (cancelled) return;
      probeResultRef.current = ok;
      setCollabReady(ok);
      onCollabStatusChange?.(ok ? "online" : "offline");
    });

    return () => { cancelled = true; };
  }, [isCollaborative, fileId, onCollabStatusChange]);

  // Effective flag: collaborative mode is only active after a successful probe.
  const effectiveCollab = isCollaborative && collabReady;

  // Build extensions based on effective mode
  const extensions = useMemo(() => {
    if (effectiveCollab && fileId) {
      // Clean up previous Yjs resources if file changed
      if (prevFileIdRef.current !== fileId) {
        if (providerRef.current) {
          providerRef.current.destroy();
          providerRef.current = null;
        }
        if (ydocRef.current) {
          ydocRef.current.destroy();
          ydocRef.current = null;
        }
      }
      prevFileIdRef.current = fileId;

      const ydoc = new Y.Doc();
      const provider = new HocuspocusProvider({
        url: getHocuspocusUrl(),
        name: `file-${fileId}`,
        document: ydoc,
      });

      ydocRef.current = ydoc;
      providerRef.current = provider;

      return [
        StarterKit.configure({ history: false }),
        Link.configure({ openOnClick: false }),
        Markdown,
        Collaboration.configure({ document: ydoc }),
        CollaborationCursor.configure({
          provider,
          user: {
            name: username || "Anonymous",
            color: userColor || "#6B7280",
          },
          render: (user) => {
            const cursor = document.createElement("span");
            cursor.classList.add("collaboration-cursor__caret");
            cursor.setAttribute("style", `border-color: ${user.color}`);

            const label = document.createElement("div");
            label.classList.add("collaboration-cursor__label");
            label.setAttribute("style", `background-color: ${user.color}`);
            label.insertBefore(document.createTextNode(user.name), null);

            cursor.insertBefore(label, null);
            return cursor;
          },
          selectionRender: (user) => {
            const hex = (user.color || "#6B7280").replace("#", "");
            const cls = `yjs-sel-${hex}`;
            if (!document.getElementById(`yjs-sel-style-${hex}`)) {
              const r = parseInt(hex.slice(0, 2), 16);
              const g = parseInt(hex.slice(2, 4), 16);
              const b = parseInt(hex.slice(4, 6), 16);
              const el = document.createElement("style");
              el.id = `yjs-sel-style-${hex}`;
              el.textContent = `.${cls} { background-color: rgba(${r}, ${g}, ${b}, 0.3) !important; }`;
              document.head.appendChild(el);
            }
            return { class: cls };
          },
        }),
      ];
    }

    // Non-collaborative / fallback
    return [
      StarterKit,
      Link.configure({ openOnClick: false }),
      Markdown,
    ];
  }, [effectiveCollab, fileId, username, userColor]);

  // Clean up Yjs resources on unmount
  useEffect(() => {
    return () => {
      if (providerRef.current) {
        providerRef.current.destroy();
        providerRef.current = null;
      }
      if (ydocRef.current) {
        ydocRef.current.destroy();
        ydocRef.current = null;
      }
    };
  }, []);

  const editor = useEditor({
    extensions,
    content: effectiveCollab ? undefined : (content || ""),
    editable: permission !== "read-only",
    onUpdate: ({ editor: ed }) => {
      if (onUpdate) {
        const md = ed.storage.markdown.getMarkdown();
        onUpdate(md);
      }
    },
  }, [extensions, effectiveCollab, fileId, permission]);

  // Seed the Yjs document with API content when it's empty after first sync.
  // This handles the case where a file is opened collaboratively for the first
  // time (no prior Yjs state exists in HocusPocus).
  useEffect(() => {
    if (!effectiveCollab || !editor || !providerRef.current || !content) return;

    const provider = providerRef.current;

    const onSync = ({ state }) => {
      if (!state) return;
      const ydoc = ydocRef.current;
      if (!ydoc) return;
      const fragment = ydoc.getXmlFragment("default");
      if (fragment.length === 0) {
        editor.commands.setContent(content);
      }
    };

    // HocusPocus provider uses 'synced' event (not 'sync')
    if (provider.isSynced) {
      onSync({ state: true });
    }
    provider.on("synced", onSync);

    return () => {
      provider.off("synced", onSync);
    };
  }, [effectiveCollab, editor, content, fileId]);

  useEffect(() => {
    if (!editorRef) return;
    if (typeof editorRef === "function") {
      editorRef(editor);
      return () => editorRef(null);
    } else {
      editorRef.current = editor;
      return () => { editorRef.current = null; };
    }
  }, [editor, editorRef]);

  // Sync content for non-collaborative mode
  useEffect(() => {
    if (!editor || content == null || effectiveCollab) return;
    const currentMd = editor.storage.markdown.getMarkdown();
    if (currentMd !== content) {
      editor.commands.setContent(content);
    }
  }, [editor, content, effectiveCollab]);

  // Update editable state when permission changes
  useEffect(() => {
    if (!editor) return;
    const shouldBeEditable = permission !== "read-only";
    if (editor.isEditable !== shouldBeEditable) {
      editor.setEditable(shouldBeEditable);
    }
  }, [editor, permission]);

  const handleContainerClick = (e) => {
    if (!editor) return;
    if (e.target === e.currentTarget || !e.target.closest(".ProseMirror")) {
      editor.commands.focus("start");
    }
  };

  return (
    <div className="tiptap-wrapper" onClick={handleContainerClick}>
      <EditorContent editor={editor} />
    </div>
  );
}
