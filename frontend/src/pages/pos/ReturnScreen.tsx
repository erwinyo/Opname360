import { useMutation, useQuery } from '@tanstack/react-query'
import { ReceiptIcon, XIcon } from 'lucide-react'
import { useRef, useState } from 'react'

import { receiptsReceiptForReturn } from '@/client'
import type {
  Cart,
  ReceiptLinePublic,
  ReceiptPublic,
  ReturnCondition,
  ShiftCurrent,
} from '@/client'
import {
  paymentMethodsListMethodsOptions,
  receiptsCompleteReceiptMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field, FormDialog } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage } from '@/lib/api'
import {
  formatDateTime,
  parseQuantity,
  quantity,
  rupiah,
  skuName,
} from '@/lib/format'
import { cn } from '@/lib/utils'

import { addOne, cartLines } from './cart'
import type { CartItem } from './cart'
import { useQuote } from './cart'
import { CartLines } from './CartLines'
import { DoneBanner } from './DoneBanner'
import { PayDialog } from './PayDialog'
import { ScanBox } from './ScanBox'
import { ShiftBar } from './ShiftBar'
import { usePrintReceipt } from './usePrintReceipt'

type Back = { quantity: string; condition: ReturnCondition }

const CONDITION_LABELS: Record<ReturnCondition, string> = {
  resellable: 'Bisa dijual lagi',
  damaged: 'Rusak',
}

/**
 * A Customer Return or an Exchange: scan the original Receipt, pick what
 * comes back, and add new goods for an exchange.
 */
export function ReturnScreen({ shift }: { shift: ShiftCurrent }) {
  const [original, setOriginal] = useState<ReceiptPublic | null>(null)
  const [backs, setBacks] = useState<Record<number, Back>>({})
  const [items, setItems] = useState<CartItem[]>([])
  const [paying, setPaying] = useState(false)
  const [settling, setSettling] = useState(false)
  const [done, setDone] = useState<ReceiptPublic | null>(null)
  const scan = useRef<HTMLInputElement>(null)
  const printer = usePrintReceipt()

  const returns = Object.entries(backs)
    .map(([lineId, back]) => ({
      original_line_id: Number(lineId),
      quantity: parseQuantity(back.quantity),
      condition: back.condition,
    }))
    .filter((line) => line.quantity > 0)
  const lines = cartLines(items)
  const cart: Cart = {
    original_receipt_id: original?.id ?? null,
    returns,
    lines,
  }
  const quote = useQuote(cart)
  const ready =
    returns.length > 0 && quote.isSuccess && !quote.isPlaceholderData
  const total = quote.data?.total ?? 0

  const start = (receipt: ReceiptPublic | null) => {
    setOriginal(receipt)
    setBacks({})
    setItems([])
  }
  const finished = (receipt: ReceiptPublic) => {
    setPaying(false)
    setSettling(false)
    start(null)
    setDone(receipt)
    printer.print(receipt.id)
  }
  const setBack = (lineId: number, change: Partial<Back>) =>
    setBacks((current) => ({
      ...current,
      [lineId]: {
        ...(current[lineId] ?? { quantity: '0', condition: 'resellable' }),
        ...change,
      },
    }))

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

      {!original ? (
        <FindReceipt
          onFound={(receipt) => {
            setDone(null)
            start(receipt)
          }}
        />
      ) : (
        <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1fr_18rem]">
          <div className="grid gap-4">
            <section className="rounded-xl border bg-card">
              <header className="flex items-start justify-between gap-3 border-b p-4">
                <div>
                  <h2 className="font-medium">
                    Retur dari struk {original.number}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {formatDateTime(original.created_at)} ·{' '}
                    {original.cashier_name} · {rupiah(original.total)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Ganti struk"
                  onClick={() => start(null)}
                >
                  <XIcon />
                </Button>
              </header>
              <ul className="divide-y">
                {original.lines
                  .filter((line) => Number(line.quantity) > 0)
                  .map((line) => (
                    <BackLine
                      key={line.id}
                      line={line}
                      back={backs[line.id]}
                      refund={
                        quote.data?.returns
                          .filter((r) => r.original_line_id === line.id)
                          .reduce((sum, r) => sum + r.refund, 0) ?? null
                      }
                      onChange={(change) => setBack(line.id, change)}
                    />
                  ))}
              </ul>
            </section>

            <section className="grid gap-3">
              <h2 className="font-medium">Barang pengganti (tukar tambah)</h2>
              <ScanBox
                inputRef={scan}
                onPick={(sku) => setItems((current) => addOne(current, sku))}
              />
              {items.length > 0 && (
                <CartLines
                  items={items}
                  quoted={quote.data?.lines ?? []}
                  highlight={null}
                  onQuantity={(skuId, value) =>
                    setItems((current) =>
                      current.map((item) =>
                        item.sku.id === skuId
                          ? { ...item, quantity: value }
                          : item,
                      ),
                    )
                  }
                  onRemove={(skuId) =>
                    setItems((current) =>
                      current.filter((item) => item.sku.id !== skuId),
                    )
                  }
                />
              )}
            </section>
          </div>

          <aside className="grid gap-3 rounded-xl border bg-card p-4 lg:sticky lg:top-6">
            <dl className="grid grid-cols-[1fr_auto] gap-y-1 tabular-nums">
              <dt className="text-muted-foreground">Retur</dt>
              <dd className="text-right">
                {rupiah(-(quote.data?.refund_total ?? 0))}
              </dd>
              <dt className="text-muted-foreground">Barang baru</dt>
              <dd className="text-right">
                {rupiah(
                  (quote.data?.subtotal ?? 0) -
                    (quote.data?.discount_total ?? 0),
                )}
              </dd>
              <dt className="mt-2 text-lg font-semibold">
                {total > 0
                  ? 'Pelanggan bayar'
                  : total < 0
                    ? 'Dikembalikan'
                    : 'Selisih'}
              </dt>
              <dd className="mt-2 text-right text-2xl font-semibold">
                {rupiah(Math.abs(total))}
              </dd>
            </dl>
            {quote.isError && (
              <p className="text-sm text-destructive">
                {errorMessage(quote.error)}
              </p>
            )}
            <Button
              size="lg"
              className="h-12 text-base"
              disabled={!ready}
              onClick={() => (total > 0 ? setPaying(true) : setSettling(true))}
            >
              {total > 0 ? 'Bayar' : 'Selesaikan'}
            </Button>
          </aside>
        </div>
      )}

      {paying && quote.data && (
        <PayDialog
          total={quote.data.total}
          cart={cart}
          onClose={() => setPaying(false)}
          onPaid={finished}
        />
      )}
      {settling && quote.data && (
        <SettleDialog
          total={quote.data.total}
          cart={cart}
          isExchange={lines.length > 0}
          onClose={() => setSettling(false)}
          onDone={finished}
        />
      )}
      {printer.slip}
    </>
  )
}

function FindReceipt({
  onFound,
}: {
  onFound: (receipt: ReceiptPublic) => void
}) {
  const [number, setNumber] = useState('')
  const find = useMutation({
    mutationFn: async (value: string) => {
      const { data } = await receiptsReceiptForReturn({
        query: { number: value },
        throwOnError: true,
      })
      return data
    },
    onSuccess: onFound,
  })
  return (
    <section className="mt-6 max-w-md">
      <h2 className="font-medium">Struk asal</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Retur dan tukar tambah selalu dari struk pembeliannya. Scan barcode di
        struk, atau ketik nomornya.
      </p>
      <div className="relative mt-3">
        <ReceiptIcon className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={number}
          onChange={(event) => setNumber(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            if (number.trim()) find.mutate(number.trim())
          }}
          placeholder="PJ-2611-0001"
          aria-label="Nomor struk"
          autoComplete="off"
          autoFocus
          className="h-12 bg-card pl-11 text-base"
        />
      </div>
      {find.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {errorMessage(find.error)}
        </p>
      )}
    </section>
  )
}

function BackLine({
  line,
  back,
  refund,
  onChange,
}: {
  line: ReceiptLinePublic
  back?: Back
  refund: number | null
  onChange: (change: Partial<Back>) => void
}) {
  const name = skuName(line)
  const left = Number(line.quantity) - Number(line.returned_quantity)
  const count = parseQuantity(back?.quantity ?? '0')
  const paidEach = line.line_total / Number(line.quantity)
  return (
    <li
      className={cn(
        'grid gap-3 p-4 sm:grid-cols-[1fr_auto]',
        count > 0 && 'bg-primary/5',
      )}
    >
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-sm text-muted-foreground tabular-nums">
          Dibeli {quantity(line.quantity)} {line.stock_unit}
          {Number(line.returned_quantity) > 0 &&
            `, sudah diretur ${quantity(line.returned_quantity)}`}{' '}
          · dibayar {rupiah(Math.round(paidEach))} / {line.stock_unit}
        </p>
        {count > 0 && refund !== null && (
          <p className="text-sm text-primary tabular-nums">
            Dikembalikan {rupiah(refund)}
          </p>
        )}
      </div>
      {left > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={back?.quantity ?? '0'}
            onChange={(event) => onChange({ quantity: event.target.value })}
            inputMode="decimal"
            aria-label={`Jumlah retur ${name}`}
            aria-invalid={count > left || !(count >= 0)}
            className="w-16 text-center tabular-nums"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange({ quantity: String(left) })}
          >
            Semua ({quantity(left)})
          </Button>
          <Select
            value={back?.condition ?? 'resellable'}
            onValueChange={(condition) =>
              onChange({ condition: condition as ReturnCondition })
            }
          >
            <SelectTrigger className="w-40" aria-label={`Kondisi ${name}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(CONDITION_LABELS) as ReturnCondition[]).map(
                (condition) => (
                  <SelectItem key={condition} value={condition}>
                    {CONDITION_LABELS[condition]}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <p className="self-center text-sm text-muted-foreground">
          Sudah diretur semua
        </p>
      )}
    </li>
  )
}

/** Nothing to pay: money goes back, or it is an even swap. */
function SettleDialog({
  total,
  cart,
  isExchange,
  onClose,
  onDone,
}: {
  total: number
  cart: Cart
  isExchange: boolean
  onClose: () => void
  onDone: (receipt: ReceiptPublic) => void
}) {
  const methods = useQuery(
    paymentMethodsListMethodsOptions({ query: { active_only: true } }),
  )
  const cash = methods.data?.find((method) => method.is_cash)
  const [methodId, setMethodId] = useState<string | null>(null)
  const chosen = methodId ?? (cash ? String(cash.id) : '')
  const complete = useMutation({
    ...receiptsCompleteReceiptMutation(),
    onSuccess: onDone,
  })
  const canChoose = total < 0 && !isExchange
  return (
    <FormDialog
      title={total < 0 ? `Kembalikan ${rupiah(-total)}` : 'Tukar tanpa selisih'}
      description={
        total === 0
          ? 'Harga barang baru sama dengan yang diretur; tidak ada uang yang berpindah.'
          : isExchange
            ? 'Selisih tukar tambah dikembalikan tunai dari laci.'
            : undefined
      }
      submitLabel="Selesaikan"
      pending={complete.isPending}
      error={complete.error}
      onSubmit={() =>
        complete.mutate({
          body: {
            ...cart,
            payments: [],
            refund_method_id: canChoose && chosen ? Number(chosen) : null,
            expected_total: total,
          },
        })
      }
      onClose={onClose}
    >
      {canChoose && (
        <Field id="refund-method" label="Dikembalikan lewat">
          <Select value={chosen} onValueChange={setMethodId}>
            <SelectTrigger id="refund-method" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {methods.data?.map((method) => (
                <SelectItem key={method.id} value={String(method.id)}>
                  {method.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
    </FormDialog>
  )
}
