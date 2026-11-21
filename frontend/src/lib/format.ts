const thousands = new Intl.NumberFormat('id-ID')
const dateTime = new Intl.DateTimeFormat('id-ID', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** 85000 -> "Rp 85.000", -10000 -> "-Rp 10.000" */
export function rupiah(amount: number): string {
  const sign = amount < 0 ? '-' : ''
  return `${sign}Rp ${thousands.format(Math.abs(amount))}`
}

/** "85000" -> "85.000", for money inputs that group digits as you type. */
export function groupDigits(digits: string): string {
  return digits ? thousands.format(Number(digits)) : ''
}

/** Keeps only the digits of what was typed into a money input. */
export function onlyDigits(text: string): string {
  return text.replace(/\D/g, '')
}

/** A quantity as the API sends it ("12.000") without trailing zeros: "12". */
export function quantity(value: string | number): string {
  return new Intl.NumberFormat('id-ID', { maximumFractionDigits: 3 }).format(
    Number(value),
  )
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}

/** "10, Putih", or "" for a SKU without variants. */
export function variantLabel(sku: {
  size?: string | null
  color?: string | null
}): string {
  return [sku.size, sku.color].filter(Boolean).join(', ')
}

const dateOnly = new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium' })

/** "2026-11-15" -> "15 Nov 2026" */
export function formatDate(isoDate: string): string {
  return dateOnly.format(new Date(`${isoDate}T00:00:00`))
}

/** A money amount as the API sends it ("120000.0000") -> "Rp 120.000". */
export function money(value: string | number): string {
  return rupiah(Math.round(Number(value)))
}

/** What was typed as a quantity ("1,5") as a number, or NaN. */
export function parseQuantity(text: string): number {
  const cleaned = text.trim().replace(',', '.')
  return cleaned === '' ? NaN : Number(cleaned)
}

/** Today in the browser's timezone as "2026-11-15", for date inputs. */
export function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

/** "Kemeja Putih SD · 10, Putih" */
export function skuName(sku: {
  product_name: string
  size?: string | null
  color?: string | null
}): string {
  return [sku.product_name, variantLabel(sku)].filter(Boolean).join(' · ')
}

/** A medicine's Batch: "Batch A12 · Kedaluwarsa 15 Nov 2027", or "". */
export function batchLabel(line: {
  batch_number?: string | null
  expires_on?: string | null
}): string {
  if (!line.batch_number) return ''
  const expiry = line.expires_on
    ? ` · Kedaluwarsa ${formatDate(line.expires_on)}`
    : ''
  return `Batch ${line.batch_number}${expiry}`
}

/** An ISO time as a `datetime-local` input wants it, in the browser's time. */
export function toLocalInput(iso: string | Date): string {
  const at = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`
}

const longDate = new Intl.DateTimeFormat('id-ID', { dateStyle: 'full' })

/** "2026-11-17" -> "Selasa, 17 November 2026" */
export function formatLongDate(isoDate: string): string {
  return longDate.format(new Date(`${isoDate}T00:00:00`))
}

const clock = new Intl.DateTimeFormat('id-ID', { timeStyle: 'short' })

/** A moment as "16.58" in the browser's time. */
export function formatTime(at: number | string | Date): string {
  return clock.format(new Date(at))
}

/** A fraction as the API sends it ("0.1234") -> "12,3%". */
export function percent(fraction: string | number): string {
  return `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(Number(fraction) * 100)}%`
}
