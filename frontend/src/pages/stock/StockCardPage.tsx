import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { stockReadStockCardOptions } from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDateTime, money, quantity, variantLabel } from '@/lib/format'
import { documentPath, REASON_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

export function StockCardPage() {
  const params = useParams()
  const skuId = Number(params.skuId)
  const [offset, setOffset] = useState(0)
  const card = useQuery({
    ...stockReadStockCardOptions({
      path: { sku_id: skuId },
      query: { offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })

  const back = (
    <Link
      to="/stok"
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeftIcon className="size-4" />
      Stok
    </Link>
  )
  if (card.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (card.isError) {
    return (
      <>
        {back}
        <p className="mt-4 text-destructive">{errorMessage(card.error)}</p>
      </>
    )
  }

  const { sku, location, items, total } = card.data
  const onHand = Number(sku.quantity)

  return (
    <>
      {back}
      <p className="mt-3 text-sm text-muted-foreground">Kartu stok</p>
      <h1 className="text-2xl font-semibold tracking-tight">
        {[sku.product_name, variantLabel(sku)].filter(Boolean).join(' · ')}
      </h1>
      <p className="mt-1 text-muted-foreground tabular-nums">
        {sku.category_name} › {sku.sub_category_name} · {sku.code} ·{' '}
        {sku.barcode} · {location.name}
      </p>

      <dl className="mt-6 grid grid-cols-2 gap-4 sm:max-w-md">
        <div className="rounded-xl border bg-card p-4">
          <dt className="text-sm text-muted-foreground">Stok sistem</dt>
          <dd
            className={cn(
              'text-xl font-semibold tabular-nums',
              onHand < 0 && 'text-destructive',
            )}
          >
            {quantity(sku.quantity)} {sku.stock_unit}
          </dd>
          {onHand < 0 && (
            <p className="mt-1 text-xs text-destructive">
              Terjual lebih banyak dari yang tercatat masuk.
            </p>
          )}
        </div>
        <div className="rounded-xl border bg-card p-4">
          <dt className="text-sm text-muted-foreground">Nilai stok</dt>
          <dd className="text-xl font-semibold tabular-nums">
            {money(sku.value)}
          </dd>
        </div>
      </dl>

      {total === 0 ? (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          Belum ada barang masuk atau keluar untuk SKU ini.
        </p>
      ) : (
        <>
          <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Waktu</TableHead>
                  <TableHead>Dokumen</TableHead>
                  <TableHead className="text-right">Masuk / keluar</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">
                    Harga pokok
                  </TableHead>
                  <TableHead className="text-right">Saldo</TableHead>
                  <TableHead className="hidden text-right md:table-cell">
                    Nilai saldo
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => {
                  const change = Number(entry.quantity)
                  const path = documentPath(
                    entry.document_type,
                    entry.document_id,
                  )
                  return (
                    <TableRow key={entry.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDateTime(entry.created_at)}
                        <span className="block text-sm text-muted-foreground">
                          {entry.created_by_name ?? 'Sistem'}
                        </span>
                      </TableCell>
                      <TableCell>
                        {path ? (
                          <Link to={path} className="font-medium tabular-nums">
                            {entry.document_number}
                          </Link>
                        ) : (
                          <span className="font-medium tabular-nums">
                            {entry.document_number}
                          </span>
                        )}
                        <span className="block text-sm text-muted-foreground">
                          {REASON_LABELS[entry.reason]}
                        </span>
                      </TableCell>
                      <TableCell
                        className={cn(
                          'text-right whitespace-nowrap tabular-nums',
                          change > 0 && 'text-primary',
                        )}
                      >
                        {change === 0
                          ? money(entry.value)
                          : `${change > 0 ? '+' : ''}${quantity(change)}`}
                      </TableCell>
                      <TableCell className="hidden text-right whitespace-nowrap tabular-nums sm:table-cell">
                        {change === 0 ? '–' : money(entry.unit_cost)}
                      </TableCell>
                      <TableCell className="text-right font-medium whitespace-nowrap tabular-nums">
                        {quantity(entry.quantity_after)}
                      </TableCell>
                      <TableCell className="hidden text-right whitespace-nowrap tabular-nums md:table-cell">
                        {money(entry.value_after)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={total}
            unit="mutasi"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
