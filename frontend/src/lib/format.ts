const thousands = new Intl.NumberFormat('id-ID')
const dateTime = new Intl.DateTimeFormat('id-ID', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** 85000 -> "Rp 85.000" */
export function rupiah(amount: number): string {
  return `Rp ${thousands.format(amount)}`
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
