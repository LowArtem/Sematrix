export type TagRef = {
  id: string
  name: string
}

export type NoteCard = {
  id: string
  title: string
  summary: string
  updated_at: string
  tags: TagRef[]
  folder_id: string | null
  status: string
  has_warnings: boolean
  warnings_count: number
  score: number | null
}

export type NoteDetail = {
  id: string
}

export type PaginatedResponse<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

type ApiErrorDto = {
  code?: string
  message?: string
}

export type ListNotesParams = {
  q: string
  folderId: string | null
  limit: number
  offset: number
}

export function buildNotesRequestPath(params: ListNotesParams): string {
  const searchParams = new URLSearchParams()

  searchParams.set("q", params.q)
  searchParams.set("limit", String(params.limit))
  searchParams.set("offset", String(params.offset))

  if (params.folderId) {
    searchParams.set("folder_id", params.folderId)
  }

  return `/api/notes?${searchParams.toString()}`
}

export async function fetchNotes(
  params: ListNotesParams,
  signal?: AbortSignal,
): Promise<PaginatedResponse<NoteCard>> {
  const response = await fetch(buildNotesRequestPath(params), {
    headers: {
      Accept: "application/json",
    },
    signal,
  })

  if (!response.ok) {
    let message = `Unable to load notes (${response.status})`

    try {
      const error = (await response.json()) as ApiErrorDto

      if (typeof error.message === "string" && error.message.trim()) {
        message = error.message
      }
    } catch {
      // Keep the fallback message when the API does not return JSON.
    }

    throw new Error(message)
  }

  return (await response.json()) as PaginatedResponse<NoteCard>
}

export async function createNote(signal?: AbortSignal): Promise<NoteDetail> {
  const response = await fetch("/api/notes", {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
    signal,
  })

  if (!response.ok) {
    let message = `Unable to create note (${response.status})`

    try {
      const error = (await response.json()) as ApiErrorDto

      if (typeof error.message === "string" && error.message.trim()) {
        message = error.message
      }
    } catch {
      // Keep the fallback message when the API does not return JSON.
    }

    throw new Error(message)
  }

  return (await response.json()) as NoteDetail
}
