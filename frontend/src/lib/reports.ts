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

type Hourly = { hour: number; receipt_count: number; cogs: string | null }

/** The shop's opening hours, and any other hour something happened. */
export function shownHours<T extends Hourly>(
  hours: T[],
  shop?: { opens_at: string; closes_at: string },
): T[] {
  const [opens, closes] = shop
    ? [hourOf(shop.opens_at), Math.ceil(hourOf(shop.closes_at))]
    : [0, 24]
  return hours.filter(
    (h) =>
      (h.hour >= Math.floor(opens) && h.hour < closes) ||
      h.receipt_count > 0 ||
      Number(h.cogs) !== 0,
  )
}

/** "21:30:00" -> 21.5 */
function hourOf(time: string): number {
  const [hour, minute] = time.split(':').map(Number)
  return hour + minute / 60
}

/** 9 -> "09.00" */
export function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, '0')}.00`
}

const compactNumber = new Intl.NumberFormat('id-ID', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

/** 1500000 -> "1,5 jt", for axes. */
export function compact(amount: number): string {
  return compactNumber.format(amount)
}

/** 9 -> "09.00–10.00" */
export function hourRange(hour: number): string {
  return `${hourLabel(hour)}–${hourLabel(hour + 1)}`
}
