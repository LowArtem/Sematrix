import Image from "@tiptap/extension-image"
import Link from "@tiptap/extension-link"
import StarterKit from "@tiptap/starter-kit"
import { EditorContent, useEditor } from "@tiptap/react"
import { useEffect, useMemo, useState } from "react"

import { getNoteDetail, listFolders, type ApiError, type Folder, type NoteDetail } from "./api"

type Route =
  | { kind: "home" }
  | { kind: "note"; noteId: string }

type LoadState =
  | { status: "loading" }
  | { status: "ready"; note: NoteDetail; folders: Folder[] }
  | { status: "error"; error: ApiError }

function toApiError(error: unknown): ApiError {
  if (typeof error === "object" && error !== null && "message" in error) {
    const maybeError = error as Partial<ApiError>
    return {
      code: maybeError.code || "request_failed",
      message: maybeError.message || "Unable to load note",
      details: maybeError.details,
    }
  }

  return {
    code: "request_failed",
    message: "Unable to load note",
  }
}

function getCurrentRoute(): Route {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/"
  const noteMatch = pathname.match(/^\/notes\/([^/]+)$/)

  if (noteMatch) {
    return { kind: "note", noteId: noteMatch[1] }
  }

  return { kind: "home" }
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function statusTone(status: string): string {
  switch (status) {
    case "Ready":
      return "is-ready"
    case "Processing":
      return "is-processing"
    case "Error":
      return "is-error"
    default:
      return "is-draft"
  }
}

function EditorToolbarButton({
  label,
  onClick,
  active = false,
  disabled = false,
}: {
  label: string
  onClick: () => void
  active?: boolean
  disabled?: boolean
}) {
  return (
    <button
      className={`toolbar-button${active ? " is-active" : ""}`}
      type="button"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  )
}

function NoteEditor({
  contentJson,
  onContentChange,
}: {
  contentJson: Record<string, unknown>
  onContentChange: (nextContent: Record<string, unknown>) => void
}) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
      }),
      Image.configure({
        inline: true,
        allowBase64: false,
        HTMLAttributes: {
          class: "note-inline-image",
        },
      }),
    ],
    content: contentJson,
    onUpdate: ({ editor: nextEditor }) => {
      onContentChange(nextEditor.getJSON() as Record<string, unknown>)
    },
  })

  useEffect(() => {
    if (!editor) {
      return
    }

    editor.commands.setContent(contentJson, false)
  }, [contentJson, editor])

  if (!editor) {
    return <div className="editor-loading">Preparing the editor...</div>
  }

  const setLink = () => {
    const previousUrl = String(editor.getAttributes("link").href ?? "")
    const nextUrl = window.prompt("Enter a link URL", previousUrl)

    if (nextUrl === null) {
      return
    }

    const trimmedUrl = nextUrl.trim()
    if (!trimmedUrl) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run()
      return
    }

    editor.chain().focus().extendMarkRange("link").setLink({ href: trimmedUrl }).run()
  }

  return (
    <div className="editor-stack">
      <div className="editor-toolbar" aria-label="Tiptap formatting toolbar">
        <EditorToolbarButton
          label="P"
          onClick={() => editor.chain().focus().setParagraph().run()}
          active={editor.isActive("paragraph")}
        />
        <EditorToolbarButton
          label="H1"
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          active={editor.isActive("heading", { level: 1 })}
        />
        <EditorToolbarButton
          label="H2"
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          active={editor.isActive("heading", { level: 2 })}
        />
        <EditorToolbarButton
          label="Bold"
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive("bold")}
        />
        <EditorToolbarButton
          label="Italic"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive("italic")}
        />
        <EditorToolbarButton
          label="Bullet"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive("bulletList")}
        />
        <EditorToolbarButton
          label="Ordered"
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive("orderedList")}
        />
        <EditorToolbarButton
          label="Quote"
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive("blockquote")}
        />
        <EditorToolbarButton
          label="Code"
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          active={editor.isActive("codeBlock")}
        />
        <EditorToolbarButton
          label="Link"
          onClick={setLink}
          active={editor.isActive("link")}
        />
        <EditorToolbarButton
          label="Unlink"
          onClick={() => editor.chain().focus().extendMarkRange("link").unsetLink().run()}
          disabled={!editor.isActive("link")}
        />
      </div>

      <div className="editor-frame">
        <EditorContent editor={editor} className="tiptap-shell" />
      </div>

      <div className="editor-caption-row">
        <span>Paragraphs, headings, lists, links, quotes, and code blocks are enabled.</span>
        <span>Inline image nodes are configured and render in the text flow when present.</span>
      </div>
    </div>
  )
}

function AppHome() {
  return (
    <main className="library-shell">
      <section className="library-card hero-card">
        <p className="overline">Sematrix</p>
        <h1>Note workspace routes are ready for editor stories.</h1>
        <p className="lead-copy">
          Open a note at <code>/notes/&lt;note-id&gt;</code> to load its backend-backed
          detail screen, folders, status, warnings, and action layout.
        </p>
        <a className="secondary-link" href="/api/notes">
          Inspect the note API
        </a>
      </section>
    </main>
  )
}

function NoteScreen({ noteId }: { noteId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" })
  const [draftContentJson, setDraftContentJson] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    setState({ status: "loading" })

    Promise.all([getNoteDetail(noteId, controller.signal), listFolders(controller.signal)])
      .then(([note, folders]) => {
        if (!controller.signal.aborted) {
          setDraftContentJson(note.content_json)
          setState({ status: "ready", note, folders })
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }

        setState({ status: "error", error: toApiError(error) })
      })

    return () => controller.abort()
  }, [noteId])

  if (state.status === "loading") {
    return (
      <main className="library-shell">
        <section className="library-card loading-card">
          <p className="overline">Loading Note</p>
          <h1>Fetching note detail and folder data...</h1>
        </section>
      </main>
    )
  }

  if (state.status === "error") {
    return (
      <main className="library-shell">
        <section className="library-card error-card">
          <p className="overline">Note Unavailable</p>
          <h1>{state.error.message}</h1>
          <p className="error-meta">Error code: {state.error.code}</p>
          <a className="secondary-link" href="/">
            Return to workspace home
          </a>
        </section>
      </main>
    )
  }

  const { note, folders } = state
  const editorContentJson = draftContentJson ?? note.content_json
  const serializedContentJson = JSON.stringify(editorContentJson, null, 2)

  return (
    <main className="note-shell">
      <header className="note-header library-card">
        <div>
          <a className="secondary-link" href="/">
            Back to workspace
          </a>
          <p className="overline">Note Detail</p>
          <h1>{note.title || "Untitled draft"}</h1>
          <p className="lead-copy">
            This screen loads the public <code>NoteDetailDto</code> contract and keeps
            folders, status, warnings, and editor content in one REST-backed view.
          </p>
        </div>

        <div className="status-cluster">
          <span className={`status-pill ${statusTone(note.status)}`}>{note.status}</span>
          <span className="meta-chip">Index v{note.index_version}</span>
          {note.has_warnings ? (
            <span className="meta-chip warning-chip">{note.warnings_count} warning(s)</span>
          ) : null}
        </div>
      </header>

      <section className="note-grid">
        <article className="library-card detail-card">
          <label className="field-block">
            <span className="field-label">Title</span>
            <input className="text-field" value={note.title} readOnly />
          </label>

          <div className="field-row">
            <label className="field-block">
              <span className="field-label">Folder</span>
              <select className="text-field" value={note.folder_id ?? ""} disabled>
                <option value="">No folder</option>
                {folders.map((folder) => (
                  <option key={folder.id} value={folder.id}>
                    {folder.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="field-block meta-block">
              <span className="field-label">Updated</span>
              <p>{formatTimestamp(note.updated_at)}</p>
              <span className="field-label sub-label">Created</span>
              <p>{formatTimestamp(note.created_at)}</p>
            </div>
          </div>

          <section className="field-block">
            <div className="section-heading">
              <span className="field-label">Tags</span>
              <span className="section-caption">Loaded from NoteDetailDto</span>
            </div>
            <div className="tag-strip">
              {note.tags.length ? (
                note.tags.map((tag) => (
                  <span key={tag.id} className="tag-chip">
                    #{tag.name}
                  </span>
                ))
              ) : (
                <span className="empty-chip">No tags yet</span>
              )}
            </div>
            <input
              className="text-field"
              value={note.tags.map((tag) => `#${tag.name}`).join(", ")}
              readOnly
            />
          </section>

          <section className="field-block">
            <div className="section-heading">
              <span className="field-label">Editor Content</span>
              <span className="section-caption">Tiptap editor with serialized JSON preview</span>
            </div>
            <NoteEditor contentJson={note.content_json} onContentChange={setDraftContentJson} />
            <textarea className="editor-surface" value={serializedContentJson} readOnly />
          </section>

          <div className="action-row">
            <button className="action-button primary-action" type="button" disabled>
              Save
            </button>
            <button className="action-button" type="button" disabled>
              Reindex
            </button>
            <button className="action-button danger-action" type="button" disabled>
              Delete
            </button>
          </div>
        </article>

        <aside className="library-card sidebar-card">
          <section className="sidebar-section">
            <div className="section-heading">
              <span className="field-label">Summary</span>
            </div>
            <p className="summary-copy">{note.summary || "No summary generated yet."}</p>
          </section>

          <section className="sidebar-section">
            <div className="section-heading">
              <span className="field-label">Warnings</span>
            </div>
            {note.processing_warnings.length ? (
              <ul className="warning-list">
                {note.processing_warnings.map((warning, index) => (
                  <li key={`${String(warning.target)}-${index}`}>
                    <strong>{String(warning.stage || "warning")}</strong>
                    <span>{String(warning.message || warning.code || "Unknown warning")}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="summary-copy">No processing warnings.</p>
            )}
          </section>

          <section className="sidebar-section">
            <div className="section-heading">
              <span className="field-label">Processing Error</span>
            </div>
            <p className="summary-copy">{note.processing_error || "No processing error."}</p>
          </section>
        </aside>
      </section>
    </main>
  )
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => getCurrentRoute())

  useEffect(() => {
    const handleRouteChange = () => setRoute(getCurrentRoute())
    window.addEventListener("popstate", handleRouteChange)
    return () => window.removeEventListener("popstate", handleRouteChange)
  }, [])

  const screen = useMemo(() => {
    if (route.kind === "note") {
      return <NoteScreen noteId={route.noteId} />
    }

    return <AppHome />
  }, [route])

  return screen
}
