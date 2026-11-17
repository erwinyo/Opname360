import { useRef, useState } from 'react'

import type { ReceiptPublic, ShiftCurrent } from '@/client'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import { rupiah, skuName } from '@/lib/format'

import { addOne, cartLines, linesAreValid, useQuote } from './cart'
import type { CartItem } from './cart'
import { CartLines } from './CartLines'
import { DoneBanner } from './DoneBanner'
import { PayDialog } from './PayDialog'
import { ScanBox } from './ScanBox'
import { ShiftBar } from './ShiftBar'
import { usePrintReceipt } from './usePrintReceipt'

/** Scan, see the total, take the payment, print the Receipt. */
export function SaleScreen({ shift }: { shift: ShiftCurrent }) {
  const [items, setItems] = useState<CartItem[]>([])
  const [lastSkuId, setLastSkuId] = useState<number | null>(null)
  const [paying, setPaying] = useState(false)
  const [done, setDone] = useState<ReceiptPublic | null>(null)
  const scan = useRef<HTMLInputElement>(null)
  const printer = usePrintReceipt()

  const lastAdded = items.find((item) => item.sku.id === lastSkuId)
  const lines = cartLines(items)
  const quote = useQuote({ lines })
  const ready =
    items.length > 0 &&
    linesAreValid(lines) &&
    quote.isSuccess &&
    !quote.isPlaceholderData
  const focusScan = () => scan.current?.focus()

  const add = (sku: CartItem['sku']) => {
    setItems((current) => addOne(current, sku))
    setLastSkuId(sku.id)
    setDone(null)
  }
  const setQuantity = (skuId: number, quantity: string) =>
    setItems((current) =>
      current.map((item) =>
        item.sku.id === skuId ? { ...item, quantity } : item,
      ),
    )
  const remove = (skuId: number) => {
    setItems((current) => current.filter((item) => item.sku.id !== skuId))
    focusScan()
  }
  const paid = (receipt: ReceiptPublic) => {
    setPaying(false)
    setItems([])
    setLastSkuId(null)
    setDone(receipt)
    printer.print(receipt.id)
    focusScan()
  }

  return (
    <>
      <ShiftBar shift={shift} />
      {done && (
        <DoneBanner
          receipt={done}
          printing={printer.printing}
          onReprint={() => printer.print(done.id)}
        />
      )}

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1fr_18rem]">
        <section className="grid gap-3">
          <ScanBox inputRef={scan} onPick={add} />
          {lastAdded && (
            <p
              role="status"
              aria-live="polite"
              className="text-sm text-muted-foreground"
            >
              {skuName(lastAdded.sku)}: {lastAdded.quantity}{' '}
              {lastAdded.sku.stock_unit}
            </p>
          )}
          {items.length > 0 ? (
            <CartLines
              items={items}
              quoted={quote.data?.lines ?? []}
              highlight={lastSkuId}
              onQuantity={setQuantity}
              onRemove={remove}
            />
          ) : (
            !done && (
              <p className="rounded-xl border border-dashed p-6 text-muted-foreground">
                Scan barang pertama untuk mulai transaksi.
              </p>
            )
          )}
        </section>

        <aside className="grid gap-3 rounded-xl border bg-card p-4 lg:sticky lg:top-6">
          <dl className="grid grid-cols-[1fr_auto] gap-y-1 tabular-nums">
            <dt className="text-muted-foreground">Subtotal</dt>
            <dd className="text-right">
              {rupiah(items.length ? (quote.data?.subtotal ?? 0) : 0)}
            </dd>
            <dt className="text-muted-foreground">Diskon</dt>
            <dd className="text-right">
              {rupiah(items.length ? -(quote.data?.discount_total ?? 0) : 0)}
            </dd>
            <dt className="mt-2 text-lg font-semibold">Total</dt>
            <dd className="mt-2 text-right text-2xl font-semibold">
              {rupiah(items.length ? (quote.data?.total ?? 0) : 0)}
            </dd>
          </dl>
          {quote.isError && items.length > 0 && (
            <p className="text-sm text-destructive">
              {errorMessage(quote.error)}
            </p>
          )}
          <Button
            size="lg"
            className="h-12 text-base"
            disabled={!ready}
            onClick={() => setPaying(true)}
          >
            Bayar
          </Button>
        </aside>
      </div>

      {paying && quote.data && (
        <PayDialog
          total={quote.data.total}
          cart={{ lines }}
          onClose={() => {
            setPaying(false)
            focusScan()
          }}
          onPaid={paid}
        />
      )}
      {printer.slip}
    </>
  )
}
