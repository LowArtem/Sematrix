import { FormEvent, useEffect, useMemo, useState } from "react"

import { buildNotesRequestPath, fetchNotes, NoteCard, PaginatedResponse } from "./api"

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

export default function App() {
  const [queryInput, setQueryInput] = useState("")
  const [submittedQuery, setSubmittedQuery] = useState("")
  const [selectedFolderId] = useState<string | null>(null)
  const [noteList, setNoteList] = useState<PaginatedResponse<NoteCard>>(emptyNoteList)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const requestPath = useMemo(
    () =>
      buildNotesRequestPath({
        q: submittedQuery,
        folderId: selectedFolderId,
        limit: PAGE_LIMIT,
        offset: 0,
      }),
    [selectedFolderId, submittedQuery],
  )

  useEffect(() => {
    const abortController = new AbortController()

    setIsLoading(true)
    setErrorMessage(null)

    fetchNotes(
      {
        q: submittedQuery,
        folderId: selectedFolderId,
        limit: PAGE_LIMIT,
        offset: 0,
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
  }, [selectedFolderId, submittedQuery])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    setSubmittedQuery(queryInput)
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
              <dd>{String(noteList.offset)}</dd>
            </div>
          </dl>
          <p className="request-path">{requestPath}</p>
        </aside>

        <section className="results-panel" aria-live="polite">
          <div className="results-header">
            <div>
              <p className="section-label">Backend results</p>
              <h2>Notes</h2>
            </div>
            <p className="result-count">{noteList.total} total</p>
          </div>

          {isLoading ? <p className="state-message">Loading notes...</p> : null}
          {errorMessage ? <p className="state-message error-state">{errorMessage}</p> : null}

          {!isLoading && !errorMessage && noteList.items.length === 0 ? (
            <p className="state-message">No notes match this query yet.</p>
          ) : null}

          {!isLoading && !errorMessage && noteList.items.length > 0 ? (
            <ul className="note-list">
              {noteList.items.map((note) => (
                <li className="note-list-item" key={note.id}>
                  <div className="note-item-header">
                    <h3>{note.title || "Untitled note"}</h3>
                    <span className="status-pill">{note.status}</span>
                  </div>
                  <p className="note-summary">{note.summary || "No summary yet."}</p>
                  <div className="note-meta-row">
                    <span>{formatUpdatedAt(note.updated_at)}</span>
                    <span>{note.tags.length} tags</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </section>
    </main>
  )
}
