import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { reportsSalesReceiptsOptions } from '@/client/@tanstack/react-query.gen'
import { BackLink } from '@/components/documents'
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
import { formatDate, formatDateTime, rupiah } from '@/lib/format'
import { RECEIPT_KIND_LABELS } from '@/lib/labels'

const PAGE_SIZE = 50

/** The Receipts behind one row of Penjualan. */
export function SalesReceiptsPage() {
  const [params] = useSearchParams()
  const [offset, setOffset] = useState(0)
  const id = (name: string) =>
    params.get(name) ? Number(params.get(name)) : undefined
  const start = params.get('start') ?? ''
  const end = params.get('end') ?? start
  const receipts = useQuery({
    ...reportsSalesReceiptsOptions({
      query: {
        start,
        end,
        cashier_id: id('cashier_id'),
        payment_method_id: id('payment_method_id'),
        category_id: id('category_id'),
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })
  const period =
    start === end
      ? formatDate(start)
      : `${formatDate(start)} s.d. ${formatDate(end)}`
  const part = params.get('category_id')
    ? 'Jumlah kategori ini'
    : params.get('payment_method_id')
      ? 'Dibayar dengan metode ini'
      : 'Total'

  return (
    <>
      <BackLink to="/laporan/penjualan" label="Penjualan" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        {params.get('label') ?? 'Struk'}
      </h1>
      <p className="mt-1 text-muted-foreground">Struk penjualan, {period}.</p>

      {receipts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(receipts.error)}</p>
      )}
      {receipts.data && (
        <>
          <div className="mt-6 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Struk</TableHead>
                  <TableHead className="hidden sm:table-cell">Kasir</TableHead>
                  <TableHead className="hidden sm:table-cell">Jenis</TableHead>
                  <TableHead className="text-right">{part}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receipts.data.items.map((receipt) => (
                  <TableRow key={receipt.id}>
                    <TableCell>
                      <Link
                        to={`/struk/${receipt.id}`}
                        className="font-medium tabular-nums"
                      >
                        {receipt.number}
                      </Link>
                      <span className="block text-xs text-muted-foreground">
                        {formatDateTime(receipt.created_at)}
                      </span>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {receipt.cashier_name}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {RECEIPT_KIND_LABELS[receipt.kind]}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {rupiah(receipt.amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={receipts.data.total}
            unit="struk"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
