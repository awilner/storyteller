import { useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Markdown } from "tiptap-markdown";

export default function TipTapEditor({ content, onUpdate, editorRef }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
      Markdown,
    ],
    content: content || "",
    onUpdate: ({ editor: ed }) => {
      if (onUpdate) {
        const md = ed.storage.markdown.getMarkdown();
        onUpdate(md);
      }
    },
  });

  // Expose editor instance via editorRef (supports both ref objects and callbacks)
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

  // Sync content prop changes into the editor
  useEffect(() => {
    if (!editor || content == null) return;
    const currentMd = editor.storage.markdown.getMarkdown();
    if (currentMd !== content) {
      editor.commands.setContent(content);
    }
  }, [editor, content]);

  const handleContainerClick = (e) => {
    if (!editor) return;
    // If the click landed on the wrapper (not inside the editable content), focus the editor
    if (e.target === e.currentTarget || !e.target.closest(".ProseMirror")) {
      editor.commands.focus("start");
    }
  };

  return (
    <div
      onClick={handleContainerClick}
      style={{
        border: "1px solid #ccc",
        borderRadius: 4,
        padding: "0.5rem",
        minHeight: 300,
        cursor: "text",
      }}
    >
      <EditorContent editor={editor} />
      <style>{`.ProseMirror { min-height: 280px; outline: none; } .ProseMirror:focus { outline: none; }`}</style>
    </div>
  );
}
