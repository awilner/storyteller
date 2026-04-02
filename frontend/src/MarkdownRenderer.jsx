import { useMemo } from "react";
import { generateHTML } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Markdown as TiptapMarkdown } from "tiptap-markdown";
import { Editor } from "@tiptap/core";

/**
 * Renders markdown content as formatted HTML using the same
 * TipTap extensions as the editor, ensuring identical output.
 */
export default function MarkdownRenderer({ content, className }) {
  const html = useMemo(() => {
    if (!content) return "";
    // Create a temporary editor to parse markdown → ProseMirror JSON → HTML
    const editor = new Editor({
      extensions: [
        StarterKit,
        Link.configure({ openOnClick: false }),
        TiptapMarkdown,
      ],
      content,
      editable: false,
    });
    const result = editor.getHTML();
    editor.destroy();
    return result;
  }, [content]);

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
