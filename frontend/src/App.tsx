import { FormEvent, useEffect, useMemo, useState } from "react"

import { buildNotesRequestPath, createNote, fetchNotes, NoteCard, PaginatedResponse } from "./api"

const PAGE_LIMIT = 12

const emptyNoteList: PaginatedResponse<NoteCard> = {
  items: [],
  total: 0,
  limit: PAGE_LIMIT,
  offset: 0,
}

function formatUpdatedAt(value: string): string {
  const parsed = new Date(value)

  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString()
}

function buildCardSummary(note: NoteCard): string {
  const trimmedSummary = note.summary.trim()

  if (trimmedSummary) {
    return trimmedSummary
  }

  if (note.tags.length > 0) {
    return `Tagged with ${note.tags.map((tag) => `#${tag.name}`).join(", ")}.`
  }

  return "Open this note to add a summary-worthy detail."
}

function buildStatusClassName(status: string): string {
  return `status-pill status-${status.toLowerCase()}`
}

function buildWarningLabel(warningsCount: number): string {
  return warningsCount === 1 ? "1 warning" : `${warningsCount} warnings`
}

export default function App() {
  const [queryInput, setQueryInput] = useState("")
  const [submittedQuery, setSubmittedQuery] = useState("")
  const [selectedFolderId] = useState<string | null>(null)
  const [paginationOffset, setPaginationOffset] = useState(0)
  const [noteList, setNoteList] = useState<PaginatedResponse<NoteCard>>(emptyNoteList)
  const [isLoading, setIsLoading] = useState(true)
  const [isCreatingNote, setIsCreatingNote] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const requestPath = useMemo(
    () =>
      buildNotesRequestPath({
        q: submittedQuery,
        folderId: selectedFolderId,
        limit: PAGE_LIMIT,
        offset: paginationOffset,
      }),
    [paginationOffset, selectedFolderId, submittedQuery],
  )

  const currentPage = Math.floor(noteList.offset / noteList.limit) + 1
  const totalPages = noteList.total === 0 ? 1 : Math.ceil(noteList.total / noteList.limit)
  const hasPreviousPage = noteList.offset > 0
  const hasNextPage = noteList.offset + noteList.limit < noteList.total

  useEffect(() => {
    const abortController = new AbortController()

    setIsLoading(true)
    setErrorMessage(null)

    fetchNotes(
      {
        q: submittedQuery,
        folderId: selectedFolderId,
        limit: PAGE_LIMIT,
        offset: paginationOffset,
      },
      abortController.signal,
    )
      .then((response) => {
        setNoteList(response)
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return
        }

        setErrorMessage(error instanceof Error ? error.message : "Unable to load notes")
        setNoteList(emptyNoteList)
      })
      .finally(() => {
        if (!abortController.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => {
      abortController.abort()
    }
  }, [paginationOffset, selectedFolderId, submittedQuery])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    setSubmittedQuery(queryInput)
    setPaginationOffset(0)
  }

  async function handleCreateNote(): Promise<void> {
    setIsCreatingNote(true)
    setErrorMessage(null)

    try {
      const note = await createNote()
      window.location.assign(`/notes/${note.id}`)
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create note")
      setIsCreatingNote(false)
    }
  }

  return (
    <main className="workspace-shell">
      <section className="topbar-panel">
        <div className="topbar-copy">
          <p className="eyebrow">Sematrix</p>
          <h1>Search every note from one field.</h1>
          <p className="lede">
            The raw query is sent straight to <code>/api/notes</code>, so free
            text and <code>#tags</code> stay backend-driven.
          </p>
        </div>

        <form className="search-form" onSubmit={handleSearchSubmit}>
          <label className="search-label" htmlFor="global-note-search">
            Global search
          </label>
          <div className="search-row">
            <input
              id="global-note-search"
              className="search-input"
              type="search"
              name="q"
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="Search notes or type #tags"
              autoComplete="off"
            />
            <button className="search-button" type="submit">
              Search
            </button>
          </div>
        </form>
      </section>

      <section className="content-grid">
        <aside className="support-panel">
          <h2>Request wiring</h2>
          <dl className="request-details">
            <div>
              <dt>q</dt>
              <dd>{submittedQuery || "(empty string)"}</dd>
            </div>
            <div>
              <dt>folder_id</dt>
              <dd>{selectedFolderId ?? "null"}</dd>
            </div>
            <div>
              <dt>limit</dt>
              <dd>{String(noteList.limit)}</dd>
            </div>
            <div>
              <dt>offset</dt>
              <dd>{String(paginationOffset)}</dd>
            </div>
          </dl>
          <p className="request-path">{requestPath}</p>
        </aside>

        <section className="results-panel" aria-live="polite">
          <div className="results-header">
            <div>
              <p className="section-label">Backend results</p>
              <h2>Notes</h2>
              <p className="results-subtitle">
                The card grid stays backend-ranked and pages through the API's
                <code> limit</code>/<code>offset</code> contract.
              </p>
            </div>
            <p className="result-count">{noteList.total} total</p>
          </div>

          {isLoading ? <p className="state-message">Loading notes...</p> : null}
          {errorMessage ? <p className="state-message error-state">{errorMessage}</p> : null}

          {!isLoading && !errorMessage && noteList.items.length === 0 ? (
            <p className="state-message">No notes match this query yet.</p>
          ) : null}

          {!errorMessage ? (
            <>
              <ul className="note-grid">
                <li>
                  <button
                    className="note-card create-note-card"
                    type="button"
                    onClick={() => {
                      void handleCreateNote()
                    }}
                    disabled={isCreatingNote}
                  >
                    <span className="create-note-plus" aria-hidden="true">
                      +
                    </span>
                    <div className="create-note-copy">
                      <p className="note-kicker">New note</p>
                      <h3>{isCreatingNote ? "Creating draft..." : "Create a fresh draft"}</h3>
                      <p className="note-summary">
                        Start with a backend draft so the editor has a real note ID before uploads.
                      </p>
                    </div>
                  </button>
                </li>
                {noteList.items.map((note) => (
                  <li className="note-card" key={note.id}>
                    <div className="note-item-header">
                      <p className="note-kicker">Note</p>
                      <div className="status-cluster">
                        <span className={buildStatusClassName(note.status)}>{note.status}</span>
                        {note.status === "Ready" && note.has_warnings ? (
                          <span className="warning-pill">{buildWarningLabel(note.warnings_count)}</span>
                        ) : null}
                      </div>
                    </div>
                    <h3>{note.title || "Untitled note"}</h3>
                    <p className="note-summary">{buildCardSummary(note)}</p>
                    <ul className="tag-list" aria-label="Note tags">
                      {note.tags.length > 0 ? (
                        note.tags.map((tag) => (
                          <li className="tag-chip" key={tag.id}>
                            #{tag.name}
                          </li>
                        ))
                      ) : (
                        <li className="tag-chip muted-tag">No tags yet</li>
                      )}
                    </ul>
                    <div className="note-meta-row">
                      <span>{formatUpdatedAt(note.updated_at)}</span>
                      <span>{note.folder_id ? "Filed note" : "Unfiled"}</span>
                    </div>
                  </li>
                ))}
              </ul>

              {noteList.items.length > 0 ? (
                <div className="pagination-bar">
                  <div>
                    <p className="section-label">Pagination</p>
                    <p className="pagination-copy">
                      Page {currentPage} of {totalPages}
                    </p>
                  </div>
                  <div className="pagination-actions">
                    <button
                      className="pagination-button"
                      type="button"
                      onClick={() => setPaginationOffset(Math.max(0, noteList.offset - noteList.limit))}
                      disabled={!hasPreviousPage}
                    >
                      Previous
                    </button>
                    <button
                      className="pagination-button"
                      type="button"
                      onClick={() => setPaginationOffset(noteList.offset + noteList.limit)}
                      disabled={!hasNextPage}
                    >
                      Next
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          ) : null}
        </section>
      </section>
    </main>
  )
}
