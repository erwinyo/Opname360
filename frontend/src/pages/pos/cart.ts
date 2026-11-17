import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { receiptsQuote } from '@/client'
import type { CartLine, TillSku } from '@/client'
import { parseQuantity } from '@/lib/format'

/** A SKU in the cart; `quantity` is what is typed, "1" or "1,5". */
export type CartItem = { sku: TillSku; quantity: string }

/** A scan adds one; scanning it again raises its quantity (rule 5). */
export function addOne(items: CartItem[], sku: TillSku): CartItem[] {
  const found = items.find((item) => item.sku.id === sku.id)
  if (!found) return [...items, { sku, quantity: '1' }]
  const next = Math.floor(parseQuantity(found.quantity) || 0) + 1
  return items.map((item) =>
    item === found ? { ...item, quantity: String(next) } : item,
  )
}

export function cartLines(items: CartItem[]): CartLine[] {
  return items.map((item) => ({
    sku_id: item.sku.id,
    quantity: parseQuantity(item.quantity),
  }))
}

export function linesAreValid(lines: CartLine[]): boolean {
  return lines.every((line) => Number(line.quantity) > 0)
}

/** Today's prices and Promotions for the cart, worked out by the server. */
export function useQuote(lines: CartLine[]) {
  return useQuery({
    queryKey: ['quote', lines],
    queryFn: async () => {
      const { data } = await receiptsQuote({
        body: { lines },
        throwOnError: true,
      })
      return data
    },
    enabled: lines.length > 0 && linesAreValid(lines),
    placeholderData: keepPreviousData,
  })
}
