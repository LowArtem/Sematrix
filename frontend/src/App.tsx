import Image from "@tiptap/extension-image"
import Link from "@tiptap/extension-link"
import StarterKit from "@tiptap/starter-kit"
import { EditorContent, useEditor } from "@tiptap/react"
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react"

import {
  deleteNote,
  getNoteDetail,
  listFolders,
  reindexNote,
  saveNote,
  type AsyncAccepted,
  uploadImage,
  type ApiError,
  type Asset,
  type Folder,
  type NoteDetail,
} from "./api"
import { normalizeTagName, normalizeTagNames } from "./tags"

type Route =
  | { kind: "home" }
  | { kind: "note"; noteId: string }

type LoadState =
  | { status: "loading" }
  | { status: "ready"; note: NoteDetail; folders: Folder[] }
  | { status: "error"; error: ApiError }

type TagAutoConvertRequest = {
  normalizedTag: string
  completionText: string
}

type TagAutoConvertRollbackHandle = {
  rollbackLatestAutoConvert: () => boolean
}

type ActionNotice = {
  tone: "success" | "error"
  message: string
}

const TAG_AUTO_CONVERT_PATTERN = /(^|[\s([{])#([0-9A-Za-zА-Яа-яЁё_]+)$/
const TAG_AUTO_CONVERT_PUNCTUATION = new Set([",", ".", "!", "?", ";", ":", ")", "]"])

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

function isAsyncAccepted(response: NoteDetail | AsyncAccepted): response is AsyncAccepted {
  return "message" in response
}

async function loadNoteScreenData(noteId: string, signal?: AbortSignal): Promise<{ note: NoteDetail; folders: Folder[] }> {
  const [note, folders] = await Promise.all([getNoteDetail(noteId, signal), listFolders(signal)])
  return { note, folders }
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

const AssetImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      assetId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-asset-id"),
        renderHTML: (attributes) => {
          if (!attributes.assetId) {
            return {}
          }

          return { "data-asset-id": String(attributes.assetId) }
        },
      },
    }
  },
})

function extractImageFiles(fileList: FileList | null): File[] {
  return Array.from(fileList ?? []).filter((file) => file.type.startsWith("image/"))
}

function getAutoConvertCompletionText(event: KeyboardEvent): string | null {
  if (event.key === " ") {
    return " "
  }

  if (event.key === "Enter") {
    return ""
  }

  if (TAG_AUTO_CONVERT_PUNCTUATION.has(event.key)) {
    return event.key
  }

  return null
}

const NoteEditor = forwardRef<TagAutoConvertRollbackHandle, {
  noteId: string
  contentJson: Record<string, unknown>
  onAutoConvertTag: (request: TagAutoConvertRequest) => void
  onClearAutoConvertRollback: () => void
  onContentChange: (nextContent: Record<string, unknown>) => void
}>(function NoteEditor({
  noteId,
  contentJson,
  onAutoConvertTag,
  onClearAutoConvertRollback,
  onContentChange,
}, ref) {
  const [uploadState, setUploadState] = useState<{ status: "idle" | "uploading" | "error"; message: string }>({
    status: "idle",
    message: "",
  })
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const isApplyingAutoConvertRef = useRef(false)
  const isRollingBackAutoConvertRef = useRef(false)
  const canRollbackAutoConvertRef = useRef(false)

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
      }),
      AssetImage.configure({
        inline: true,
        allowBase64: false,
        HTMLAttributes: {
          class: "note-inline-image",
        },
      }),
    ],
    content: contentJson,
    editorProps: {
      handleKeyDown: (_view, event) => {
        const completionText = getAutoConvertCompletionText(event)
        if (!completionText || !editor) {
          return false
        }

        if (editor.isActive("link") || editor.isActive("code") || editor.isActive("codeBlock")) {
          return false
        }

        const { state } = editor
        const { selection } = state

        if (!selection.empty) {
          return false
        }

        const { $from } = selection
        const textBeforeCursor = $from.parent.textBetween(0, $from.parentOffset, undefined, "\ufffc")
        const match = textBeforeCursor.match(TAG_AUTO_CONVERT_PATTERN)

        if (!match) {
          return false
        }

        try {
          const normalizedTag = normalizeTagName(match[2])
          const tokenStart = textBeforeCursor.length - match[0].length + match[1].length
          const deleteFrom = $from.start() + tokenStart
          const deleteTo = selection.from

          event.preventDefault()
          isApplyingAutoConvertRef.current = true
          editor
            .chain()
            .focus()
            .command(({ tr, dispatch }) => {
              tr.delete(deleteFrom, deleteTo)
              if (completionText) {
                tr.insertText(completionText, deleteFrom)
              }
              if (dispatch) {
                dispatch(tr)
              }
              return true
            })
            .run()
          onAutoConvertTag({ normalizedTag, completionText })
          return true
        } catch {
          return false
        }
      },
      handlePaste: (_view, event) => {
        const imageFiles = extractImageFiles(event.clipboardData?.files ?? null)
        if (!imageFiles.length) {
          return false
        }

        event.preventDefault()
        void uploadAndInsertFiles(imageFiles)
        return true
      },
      handleDrop: (_view, event) => {
        const imageFiles = extractImageFiles(event.dataTransfer?.files ?? null)
        if (!imageFiles.length) {
          return false
        }

        event.preventDefault()
        void uploadAndInsertFiles(imageFiles)
        return true
      },
    },
    onUpdate: ({ editor: nextEditor }) => {
      onContentChange(nextEditor.getJSON() as Record<string, unknown>)

      if (isApplyingAutoConvertRef.current) {
        isApplyingAutoConvertRef.current = false
        canRollbackAutoConvertRef.current = true
        return
      }

      if (isRollingBackAutoConvertRef.current) {
        isRollingBackAutoConvertRef.current = false
        return
      }

      if (canRollbackAutoConvertRef.current) {
        canRollbackAutoConvertRef.current = false
        onClearAutoConvertRollback()
      }
    },
  })

  useImperativeHandle(ref, () => ({
    rollbackLatestAutoConvert: () => {
      if (!editor || !canRollbackAutoConvertRef.current) {
        return false
      }

      canRollbackAutoConvertRef.current = false
      isRollingBackAutoConvertRef.current = true
      return editor.chain().focus().undo().run()
    },
  }), [editor])

  const insertUploadedImage = (asset: Asset, assetAlt: string) => {
    if (!editor) {
      return
    }

    const imageAttributes = { src: asset.url, alt: assetAlt, assetId: asset.id }

    editor
      .chain()
      .focus()
      .insertContent({ type: "image", attrs: imageAttributes })
      .run()
  }

  const uploadAndInsertFiles = async (imageFiles: File[]) => {
    if (!imageFiles.length) {
      return
    }

    setUploadState({ status: "uploading", message: "Uploading image..." })

    try {
      for (const imageFile of imageFiles) {
        const asset = await uploadImage(noteId, imageFile)
        insertUploadedImage(asset, imageFile.name)
      }

      setUploadState({ status: "idle", message: "" })
    } catch (error) {
      const nextError = toApiError(error)
      setUploadState({ status: "error", message: nextError.message })
    }
  }

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

  const openImagePicker = () => {
    fileInputRef.current?.click()
  }

  const handleImageInputChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const imageFiles = extractImageFiles(event.target.files)
    event.target.value = ""
    await uploadAndInsertFiles(imageFiles)
  }

  return (
    <div className="editor-stack">
      <input
        ref={fileInputRef}
        className="sr-only-file-input"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/*"
        multiple
        onChange={handleImageInputChange}
      />

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
          label="Image"
          onClick={openImagePicker}
          disabled={uploadState.status === "uploading"}
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
        <span>Insert images with the toolbar, drag-and-drop, or clipboard paste.</span>
      </div>

      {uploadState.status === "uploading" ? (
        <p className="editor-upload-message">Uploading image...</p>
      ) : null}
      {uploadState.status === "error" ? (
        <p className="editor-upload-error">{uploadState.message}</p>
      ) : null}
    </div>
  )
})

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
  const [draftTitle, setDraftTitle] = useState("")
  const [draftFolderId, setDraftFolderId] = useState<string | null>(null)
  const [draftContentJson, setDraftContentJson] = useState<Record<string, unknown> | null>(null)
  const [draftTags, setDraftTags] = useState<string[] | null>(null)
  const [pendingAutoConvertRollback, setPendingAutoConvertRollback] = useState<{
    normalizedTag: string
    tagWasAdded: boolean
  } | null>(null)
  const [tagInput, setTagInput] = useState("")
  const [tagError, setTagError] = useState<string | null>(null)
  const [activeAction, setActiveAction] = useState<"saving" | "reindexing" | "deleting" | null>(null)
  const [actionNotice, setActionNotice] = useState<ActionNotice | null>(null)
  const editorRef = useRef<TagAutoConvertRollbackHandle | null>(null)
  const tagInputRef = useRef<HTMLInputElement | null>(null)

  function applyLoadedNote(nextNote: NoteDetail): void {
    setDraftTitle(nextNote.title)
    setDraftFolderId(nextNote.folder_id)
    setDraftContentJson(nextNote.content_json)
    setDraftTags(normalizeTagNames(nextNote.tags.map((tag) => tag.name)))
    setPendingAutoConvertRollback(null)
    setTagInput("")
    setTagError(null)
  }

  function updateLoadedNote(nextNote: NoteDetail, folders: Folder[]): void {
    applyLoadedNote(nextNote)
    setState({ status: "ready", note: nextNote, folders })
  }

  async function refreshLoadedNote(folders: Folder[]): Promise<NoteDetail | null> {
    try {
      const refreshedNote = await getNoteDetail(noteId)
      updateLoadedNote(refreshedNote, folders)
      return refreshedNote
    } catch {
      return null
    }
  }

  useEffect(() => {
    const controller = new AbortController()

    setState({ status: "loading" })

    loadNoteScreenData(noteId, controller.signal)
      .then(({ note, folders }) => {
        if (!controller.signal.aborted) {
          updateLoadedNote(note, folders)
          setActionNotice(null)
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
  const displayedTitle = draftTitle
  const displayedFolderId = draftFolderId
  const editorContentJson = draftContentJson ?? note.content_json
  const displayedTags = draftTags ?? normalizeTagNames(note.tags.map((tag) => tag.name))
  const serializedContentJson = JSON.stringify(editorContentJson, null, 2)

  function clearPendingAutoConvertRollback(): void {
    setPendingAutoConvertRollback(null)
  }

  async function handleSave(): Promise<void> {
    setActiveAction("saving")
    setActionNotice(null)

    try {
      const response = await saveNote(note.id, {
        title: draftTitle,
        folder_id: draftFolderId,
        tags: displayedTags,
        content_json: editorContentJson,
      })

      if (isAsyncAccepted(response)) {
        const refreshedNote = await refreshLoadedNote(folders)
        if (!refreshedNote) {
          setState({
            status: "ready",
            note: {
              ...note,
              title: draftTitle,
              folder_id: draftFolderId,
              tags: displayedTags.map((tagName) => {
                const existingTag = note.tags.find((tag) => tag.name === tagName)
                return existingTag ?? { id: `draft-${tagName}`, name: tagName }
              }),
              content_json: editorContentJson,
              status: response.status,
              index_version: response.index_version,
            },
            folders,
          })
        }

        setActionNotice({ tone: "success", message: response.message })
        return
      }

      updateLoadedNote(response, folders)
      setActionNotice({ tone: "success", message: "Note saved without starting background processing." })
    } catch (error) {
      setActionNotice({ tone: "error", message: toApiError(error).message })
    } finally {
      setActiveAction(null)
    }
  }

  async function handleReindex(): Promise<void> {
    setActiveAction("reindexing")
    setActionNotice(null)

    try {
      const response = await reindexNote(note.id)
      const refreshedNote = await refreshLoadedNote(folders)

      if (!refreshedNote) {
        setState({
          status: "ready",
          note: {
            ...note,
            status: response.status,
            index_version: response.index_version,
          },
          folders,
        })
      }

      setActionNotice({ tone: "success", message: response.message })
    } catch (error) {
      setActionNotice({ tone: "error", message: toApiError(error).message })
    } finally {
      setActiveAction(null)
    }
  }

  async function handleDelete(): Promise<void> {
    if (!window.confirm("Delete this note permanently?")) {
      return
    }

    setActiveAction("deleting")
    setActionNotice(null)

    try {
      await deleteNote(note.id)
      window.location.assign("/")
    } catch (error) {
      setActionNotice({ tone: "error", message: toApiError(error).message })
      setActiveAction(null)
    }
  }

  function rollbackLatestAutoConvert(): void {
    if (!pendingAutoConvertRollback) {
      return
    }

    const rollbackApplied = editorRef.current?.rollbackLatestAutoConvert()
    if (!rollbackApplied) {
      setPendingAutoConvertRollback(null)
      return
    }

    if (pendingAutoConvertRollback.tagWasAdded) {
      setDraftTags((currentTags) =>
        normalizeTagNames(
          (currentTags ?? displayedTags).filter(
            (currentTag) => currentTag !== pendingAutoConvertRollback.normalizedTag,
          ),
        ),
      )
    }

    setPendingAutoConvertRollback(null)
    setTagInput("")
    setTagError(null)
  }

  function handleAddTag(): void {
    try {
      const normalizedTag = normalizeTagName(tagInput)

      if (displayedTags.includes(normalizedTag)) {
        setTagError("This tag is already on the note")
        return
      }

      setDraftTags((currentTags) => [...(currentTags ?? []), normalizedTag])
      clearPendingAutoConvertRollback()
      setTagInput("")
      setTagError(null)
    } catch (error) {
      setTagError(error instanceof Error ? error.message : "Unable to add tag")
    }
  }

  function handleRemoveTag(tagName: string): void {
    setDraftTags((currentTags) => (currentTags ?? []).filter((currentTag) => currentTag !== tagName))
    clearPendingAutoConvertRollback()
    setTagError(null)
  }

  function handleAutoConvertTag({ normalizedTag }: TagAutoConvertRequest): void {
    const tagWasAdded = !displayedTags.includes(normalizedTag)
    setDraftTags((currentTags) => normalizeTagNames([...(currentTags ?? displayedTags), normalizedTag]))
    setPendingAutoConvertRollback({ normalizedTag, tagWasAdded })
    setTagInput("")
    setTagError(null)
    window.setTimeout(() => {
      tagInputRef.current?.focus()
    }, 0)
  }

  return (
    <main className="note-shell">
      <header className="note-header library-card">
        <div>
          <a className="secondary-link" href="/">
            Back to workspace
          </a>
          <p className="overline">Note Detail</p>
          <h1>{displayedTitle || "Untitled draft"}</h1>
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
            <input className="text-field" value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} />
          </label>

          <div className="field-row">
            <label className="field-block">
              <span className="field-label">Folder</span>
              <select
                className="text-field"
                value={displayedFolderId ?? ""}
                onChange={(event) => setDraftFolderId(event.target.value || null)}
              >
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
              <span className="section-caption">Add tags manually with backend-matching rules</span>
            </div>
            <div className="tag-strip">
              {displayedTags.length ? (
                displayedTags.map((tagName) => (
                  <button
                    key={tagName}
                    className="tag-chip tag-chip-button"
                    type="button"
                    onClick={() => handleRemoveTag(tagName)}
                  >
                    <span>#{tagName}</span>
                    <span className="tag-chip-remove" aria-hidden="true">
                      ×
                    </span>
                  </button>
                ))
              ) : (
                <span className="empty-chip">No tags yet</span>
              )}
            </div>

            <div className="tag-editor-row">
              <input
                ref={tagInputRef}
                className="text-field"
                value={tagInput}
                onChange={(event) => {
                  setTagInput(event.target.value)
                  if (pendingAutoConvertRollback) {
                    clearPendingAutoConvertRollback()
                  }
                  if (tagError) {
                    setTagError(null)
                  }
                }}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z" && pendingAutoConvertRollback) {
                    event.preventDefault()
                    rollbackLatestAutoConvert()
                    return
                  }

                  if (event.key === "Backspace" && !tagInput && pendingAutoConvertRollback) {
                    event.preventDefault()
                    rollbackLatestAutoConvert()
                    return
                  }

                  if (event.key === "Enter") {
                    event.preventDefault()
                    handleAddTag()
                  }
                }}
                placeholder="Add a tag like research_notes"
                aria-label="Add a tag"
              />
              <button className="action-button tag-add-button" type="button" onClick={handleAddTag}>
                Add tag
              </button>
            </div>

            <p className="field-hint">Tags are trimmed, lowercased, and may use Latin/Cyrillic letters, digits, and underscore.</p>
            {tagError ? <p className="field-error">{tagError}</p> : null}
          </section>

          <section className="field-block">
            <div className="section-heading">
              <span className="field-label">Editor Content</span>
              <span className="section-caption">Type a valid #tag and finish with space, Enter, or punctuation to convert it into a note tag.</span>
            </div>
            <NoteEditor
              ref={editorRef}
              noteId={note.id}
              contentJson={editorContentJson}
              onAutoConvertTag={handleAutoConvertTag}
              onClearAutoConvertRollback={clearPendingAutoConvertRollback}
              onContentChange={setDraftContentJson}
            />
            <textarea className="editor-surface" value={serializedContentJson} readOnly />
          </section>

          {actionNotice ? (
            <p className={`action-notice ${actionNotice.tone === "error" ? "is-error" : "is-success"}`}>
              {actionNotice.message}
            </p>
          ) : null}

          <div className="action-row">
            <button
              className="action-button primary-action"
              type="button"
              onClick={() => void handleSave()}
              disabled={activeAction !== null}
            >
              {activeAction === "saving" ? "Saving..." : "Save"}
            </button>
            <button
              className="action-button"
              type="button"
              onClick={() => void handleReindex()}
              disabled={activeAction !== null}
            >
              {activeAction === "reindexing" ? "Reindexing..." : "Reindex"}
            </button>
            <button
              className="action-button danger-action"
              type="button"
              onClick={() => void handleDelete()}
              disabled={activeAction !== null}
            >
              {activeAction === "deleting" ? "Deleting..." : "Delete"}
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
