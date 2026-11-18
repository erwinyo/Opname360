import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { supplierPaymentsListDebtsOptions } from '@/client/@tanstack/react-query.gen'
import { Empty } from '@/components/reports'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate, rupiah } from '@/lib/format'

/** Hutang Usaha: what is owed per Supplier and Goods Receipt. */
export function DebtsPage() {
  const debts = useQuery(supplierPaymentsListDebtsOptions())
  const total = debts.data?.reduce((sum, debt) => sum + debt.owed, 0) ?? 0
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Hutang Usaha
          </h1>
          <p className="mt-1 text-muted-foreground">
            Barang masuk yang belum lunas per pemasok, setelah retur dan
            pembayaran.
          </p>
        </div>
        {debts.data && (
          <div className="sm:text-right">
            <p className="text-sm text-muted-foreground">Total hutang</p>
            <p className="text-xl font-semibold tabular-nums">
              {rupiah(total)}
            </p>
          </div>
        )}
      </div>
      {debts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(debts.error)}</p>
      )}
      {debts.data && debts.data.length === 0 && (
        <Empty>Tidak ada hutang ke pemasok.</Empty>
      )}
      {debts.data?.map((debt) => (
        <section key={debt.supplier_id} className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">
              {debt.supplier_name}{' '}
              <span className="font-normal text-muted-foreground tabular-nums">
                {rupiah(debt.owed)}
              </span>
            </h2>
            <Button variant="outline" size="sm" asChild>
              <Link to={`/bayar-hutang?pemasok=${debt.supplier_id}`}>
                Bayar
              </Link>
            </Button>
          </div>
          <div className="mt-2 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Barang masuk</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">
                    Total
                  </TableHead>
                  <TableHead className="hidden text-right md:table-cell">
                    Retur
                  </TableHead>
                  <TableHead className="hidden text-right md:table-cell">
                    Dibayar
                  </TableHead>
                  <TableHead className="text-right">Sisa</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {debt.receipts.map((row) => (
                  <TableRow key={row.goods_receipt_id ?? 'awal'}>
                    <TableCell>
                      {row.goods_receipt_id ? (
                        <Link
                          to={`/barang-masuk/${row.goods_receipt_id}`}
                          className="font-medium tabular-nums"
                        >
                          {row.number}
                        </Link>
                      ) : (
                        <span className="font-medium">Saldo awal hutang</span>
                      )}
                      <span className="block text-xs text-muted-foreground">
                        {[
                          row.received_on && formatDate(row.received_on),
                          row.supplier_invoice,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums sm:table-cell">
                      {rupiah(row.total)}
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {row.returned ? rupiah(row.returned) : ''}
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {row.paid ? rupiah(row.paid) : ''}
                    </TableCell>
                    <TableCell className="text-right font-medium whitespace-nowrap tabular-nums">
                      {rupiah(row.owed)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      ))}
    </>
  )
}
