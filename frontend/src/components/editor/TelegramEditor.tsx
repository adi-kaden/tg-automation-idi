'use client';

import { useCallback, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import CharacterCount from '@tiptap/extension-character-count';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Bold, Italic, Quote, Link2, X } from 'lucide-react';

// ---------------------------------------------------------------------------
// HTML post-processor: converts ProseMirror output → Telegram-compatible HTML
// ---------------------------------------------------------------------------
function toTelegramHTML(html: string): string {
  return html
    // Strip opening <p> tags
    .replace(/<p>/g, '')
    // Replace closing </p> with newline
    .replace(/<\/p>/g, '\n')
    // <strong> → <b>
    .replace(/<strong>/g, '<b>')
    .replace(/<\/strong>/g, '</b>')
    // <em> → <i>
    .replace(/<em>/g, '<i>')
    .replace(/<\/em>/g, '</i>')
    // Remove trailing newlines
    .replace(/\n+$/, '')
    .trim();
}

// ---------------------------------------------------------------------------
// Reverse: convert Telegram HTML → ProseMirror-compatible HTML for loading
// ---------------------------------------------------------------------------
function fromTelegramHTML(html: string): string {
  if (!html) return '';
  // If it already looks like ProseMirror output (starts with <p>), leave it
  if (html.trimStart().startsWith('<p>')) return html;

  return html
    // <b> → <strong>
    .replace(/<b>/g, '<strong>')
    .replace(/<\/b>/g, '</strong>')
    // <i> → <em>
    .replace(/<i>/g, '<em>')
    .replace(/<\/i>/g, '</em>')
    // Split by newlines and wrap each line in <p>
    .split('\n')
    .map((line) => `<p>${line || '<br>'}</p>`)
    .join('');
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface TelegramEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Link input popover state
// ---------------------------------------------------------------------------
interface LinkPopoverState {
  open: boolean;
  url: string;
}

// ---------------------------------------------------------------------------
// TelegramEditor component
// ---------------------------------------------------------------------------
export function TelegramEditor({
  content,
  onChange,
  placeholder = 'Введите текст поста...',
  className = '',
}: TelegramEditorProps) {
  const [linkPopover, setLinkPopover] = useState<LinkPopoverState>({
    open: false,
    url: '',
  });

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Disable heading, code, codeBlock, horizontalRule – not needed for Telegram
        heading: false,
        codeBlock: false,
        code: false,
        horizontalRule: false,
        // Keep bold, italic, blockquote, paragraph, hardBreak, listItem
      }),
      Link.configure({
        openOnClick: false,
        autolink: false,
        HTMLAttributes: {
          rel: null,
          target: null,
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
      CharacterCount,
    ],
    content: fromTelegramHTML(content),
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange(toTelegramHTML(html));
    },
    editorProps: {
      attributes: {
        class:
          'min-h-[200px] px-3 py-3 focus:outline-none prose prose-sm max-w-none text-slate-800',
      },
    },
  });

  // ------------------------------------------------------------------
  // Link actions
  // ------------------------------------------------------------------
  const openLinkPopover = useCallback(() => {
    const existingHref = editor?.getAttributes('link').href ?? '';
    setLinkPopover({ open: true, url: existingHref });
  }, [editor]);

  const applyLink = useCallback(() => {
    if (!editor) return;
    const url = linkPopover.url.trim();
    if (!url) {
      editor.chain().focus().unsetLink().run();
    } else {
      editor
        .chain()
        .focus()
        .setLink({ href: url })
        .run();
    }
    setLinkPopover({ open: false, url: '' });
  }, [editor, linkPopover.url]);

  const cancelLink = useCallback(() => {
    setLinkPopover({ open: false, url: '' });
  }, []);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  if (!editor) return null;

  return (
    <div className={`border rounded-md overflow-hidden focus-within:ring-2 focus-within:ring-ring ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b bg-slate-50">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          isActive={editor.isActive('bold')}
          title="Жирный (Ctrl+B)"
        >
          <Bold className="h-4 w-4" />
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          isActive={editor.isActive('italic')}
          title="Курсив (Ctrl+I)"
        >
          <Italic className="h-4 w-4" />
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          isActive={editor.isActive('blockquote')}
          title="Цитата"
        >
          <Quote className="h-4 w-4" />
        </ToolbarButton>

        <div className="w-px h-5 bg-slate-200 mx-0.5" />

        <ToolbarButton
          onClick={openLinkPopover}
          isActive={editor.isActive('link')}
          title="Ссылка"
        >
          <Link2 className="h-4 w-4" />
        </ToolbarButton>

        {editor.isActive('link') && (
          <ToolbarButton
            onClick={() => editor.chain().focus().unsetLink().run()}
            isActive={false}
            title="Убрать ссылку"
          >
            <X className="h-4 w-4" />
          </ToolbarButton>
        )}
      </div>

      {/* Link URL input */}
      {linkPopover.open && (
        <div className="flex items-center gap-2 px-3 py-2 border-b bg-slate-50">
          <Input
            autoFocus
            type="url"
            placeholder="https://..."
            value={linkPopover.url}
            onChange={(e) => setLinkPopover((s) => ({ ...s, url: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applyLink();
              if (e.key === 'Escape') cancelLink();
            }}
            className="h-8 text-sm flex-1"
          />
          <Button size="sm" variant="default" className="h-8 px-3 text-xs" onClick={applyLink}>
            OK
          </Button>
          <Button size="sm" variant="ghost" className="h-8 px-2" onClick={cancelLink}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Editor area */}
      <EditorContent editor={editor} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolbarButton helper
// ---------------------------------------------------------------------------
function ToolbarButton({
  onClick,
  isActive,
  title,
  children,
}: {
  onClick: () => void;
  isActive: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`
        inline-flex items-center justify-center rounded h-7 w-7 text-sm transition-colors
        ${
          isActive
            ? 'bg-slate-200 text-slate-900'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
        }
      `}
    >
      {children}
    </button>
  );
}

export default TelegramEditor;
