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

  useEffect(() => {
    const controller = new AbortController()

    setState({ status: "loading" })

    Promise.all([getNoteDetail(noteId, controller.signal), listFolders(controller.signal)])
      .then(([note, folders]) => {
        if (!controller.signal.aborted) {
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
  const contentJson = JSON.stringify(note.content_json, null, 2)

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
              <span className="section-caption">Current JSON document payload</span>
            </div>
            <textarea className="editor-surface" value={contentJson} readOnly />
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
