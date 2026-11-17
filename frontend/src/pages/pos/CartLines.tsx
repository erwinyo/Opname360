import { MinusIcon, PlusIcon, Trash2Icon } from 'lucide-react'

import type { QuotedLine } from '@/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { parseQuantity, rupiah, skuName } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { CartItem } from './cart'

export function CartLines({
  items,
  quoted,
  highlight,
  onQuantity,
  onRemove,
}: {
  items: CartItem[]
  quoted: QuotedLine[]
  highlight: number | null
  onQuantity: (skuId: number, quantity: string) => void
  onRemove: (skuId: number) => void
}) {
  const bySku = new Map(quoted.map((line) => [line.sku_id, line]))
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {items.map((item) => {
        const line = bySku.get(item.sku.id)
        const name = skuName(item.sku)
        const quantity = parseQuantity(item.quantity)
        return (
          <li
            key={item.sku.id}
            className={cn(
              'grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 p-3 sm:grid-cols-[1fr_auto_7rem_auto]',
              item.sku.id === highlight && 'bg-primary/5',
            )}
          >
            <div className="min-w-0">
              <p className="font-medium">{name}</p>
              <p className="text-sm text-muted-foreground tabular-nums">
                {item.sku.code} · {rupiah(item.sku.selling_price)} /{' '}
                {item.sku.stock_unit}
              </p>
              {line?.promotion_name && line.discount > 0 && (
                <p className="text-sm text-primary">
                  {line.promotion_name}: -{rupiah(line.discount)}
                </p>
              )}
            </div>
            <div className="row-start-2 flex items-center gap-1 sm:row-start-auto">
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Kurangi ${name}`}
                disabled={!(quantity > 1)}
                onClick={() =>
                  onQuantity(item.sku.id, String(Math.ceil(quantity) - 1))
                }
              >
                <MinusIcon />
              </Button>
              <Input
                value={item.quantity}
                onChange={(event) =>
                  onQuantity(item.sku.id, event.target.value)
                }
                inputMode="decimal"
                aria-label={`Jumlah ${name}`}
                aria-invalid={!(quantity > 0)}
                className="w-16 text-center tabular-nums"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Tambah ${name}`}
                onClick={() =>
                  onQuantity(item.sku.id, String(Math.floor(quantity || 0) + 1))
                }
              >
                <PlusIcon />
              </Button>
            </div>
            <p className="self-center text-right font-medium tabular-nums">
              {line ? rupiah(line.line_total) : '…'}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Hapus ${name}`}
              className="row-start-2 justify-self-end sm:row-start-auto"
              onClick={() => onRemove(item.sku.id)}
            >
              <Trash2Icon />
            </Button>
          </li>
        )
      })}
    </ul>
  )
}
