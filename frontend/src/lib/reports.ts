export const ALL = 'all'

/** The API path with the filters that are set, for an Excel link. */
export function withQuery(
  path: string,
  query: Record<string, string | number | undefined>,
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value))
  }
  return `/api/v1/${path}?${params}`
}

/** A Select value as a filter: `undefined` for "all". */
export function chosen(value: string): number | undefined {
  return value === ALL ? undefined : Number(value)
}
