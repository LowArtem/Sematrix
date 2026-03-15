const TAG_NAME_PATTERN = /^[0-9A-Za-zА-Яа-яЁё_]+$/

export function normalizeTagName(value: string): string {
  const normalized = value.trim().toLowerCase()

  if (!normalized) {
    throw new Error("Tag name cannot be empty")
  }

  if (/\s/.test(normalized)) {
    throw new Error("Tag name cannot contain spaces")
  }

  if (!TAG_NAME_PATTERN.test(normalized)) {
    throw new Error("Tag name may contain only Latin/Cyrillic letters, digits, and underscore")
  }

  return normalized
}

export function normalizeTagNames(values: string[]): string[] {
  const seen = new Set<string>()
  const normalizedValues: string[] = []

  for (const value of values) {
    const normalized = normalizeTagName(value)

    if (seen.has(normalized)) {
      continue
    }

    seen.add(normalized)
    normalizedValues.push(normalized)
  }

  return normalizedValues
}
