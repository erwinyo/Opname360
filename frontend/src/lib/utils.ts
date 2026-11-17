export { cn } from 'cn'

/** `ids` with `id` added, or taken out if it was there. */
export function toggle(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
}
