import { useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Markdown } from "tiptap-markdown";
import "./TipTapEditor.css";

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

  useEffect(() => {
    if (!editor || content == null) return;
    const currentMd = editor.storage.markdown.getMarkdown();
    if (currentMd !== content) {
      editor.commands.setContent(content);
    }
  }, [editor, content]);

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
