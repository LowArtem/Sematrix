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

async function readJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)

  if (!response.ok) {
    let errorPayload: ApiError | null = null

    try {
      errorPayload = (await response.json()) as ApiError
    } catch {
      errorPayload = null
    }

    throw errorPayload ?? {
      code: `http_${response.status}`,
      message: response.statusText || "Request failed",
    }
  }

  return (await response.json()) as T
}

export function getNoteDetail(noteId: string, signal?: AbortSignal): Promise<NoteDetail> {
  return readJson<NoteDetail>(`/api/notes/${noteId}`, { signal })
}

export function listFolders(signal?: AbortSignal): Promise<Folder[]> {
  return readJson<Folder[]>("/api/folders", { signal })
}
