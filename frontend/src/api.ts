export type ApiError = {
  code: string
  message: string
  details?: unknown
}

export type TagRef = {
  id: string
  name: string
}

export type NoteDetail = {
  id: string
  created_at: string
  updated_at: string
  title: string
  summary: string
  folder_id: string | null
  tags: TagRef[]
  content_json: Record<string, unknown>
  status: string
  processing_error: string | null
  has_warnings: boolean
  warnings_count: number
  processing_warnings: Array<Record<string, unknown>>
  index_version: number
}

export type Folder = {
  id: string
  name: string
  created_at: string
  updated_at: string
  notes_count: number | null
}

export type AsyncAccepted = {
  id: string
  status: string
  index_version: number
  message: string
}

export type Asset = {
  id: string
  mime_type: string
  size_bytes: number
  url: string
}

export type NoteSavePayload = {
  title: string
  folder_id: string | null
  tags: string[]
  content_json: Record<string, unknown>
}

export type SaveNoteResponse = NoteDetail | AsyncAccepted

async function readApiError(response: Response): Promise<ApiError> {
  try {
    return (await response.json()) as ApiError
  } catch {
    return {
      code: `http_${response.status}`,
      message: response.statusText || "Request failed",
    }
  }
}

async function readJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)

  if (!response.ok) {
    throw await readApiError(response)
  }

  return (await response.json()) as T
}

export function getNoteDetail(noteId: string, signal?: AbortSignal): Promise<NoteDetail> {
  return readJson<NoteDetail>(`/api/notes/${noteId}`, { signal })
}

export function listFolders(signal?: AbortSignal): Promise<Folder[]> {
  return readJson<Folder[]>("/api/folders", { signal })
}

export function uploadImage(noteId: string, file: File, signal?: AbortSignal): Promise<Asset> {
  const formData = new FormData()
  formData.append("note_id", noteId)
  formData.append("file", file)

  return readJson<Asset>("/api/assets/image", {
    method: "POST",
    body: formData,
    signal,
  })
}

export function saveNote(noteId: string, payload: NoteSavePayload, signal?: AbortSignal): Promise<SaveNoteResponse> {
  return readJson<SaveNoteResponse>(`/api/notes/${noteId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  })
}

export function reindexNote(noteId: string, signal?: AbortSignal): Promise<AsyncAccepted> {
  return readJson<AsyncAccepted>(`/api/notes/${noteId}/reindex`, {
    method: "POST",
    signal,
  })
}

export async function deleteNote(noteId: string, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`/api/notes/${noteId}`, {
    method: "DELETE",
    signal,
  })

  if (!response.ok) {
    throw await readApiError(response)
  }
}
