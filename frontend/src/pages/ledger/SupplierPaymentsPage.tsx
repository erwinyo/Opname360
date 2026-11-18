import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import type { OwedReceipt, SupplierPaymentPublic } from '@/client'
import {
  supplierPaymentsCreatePaymentMutation,
  supplierPaymentsListDebtsOptions,
  supplierPaymentsListPaymentsOptions,
  supplierPaymentsReversePaymentMutation,
} from '@/client/@tanstack/react-query.gen'
import { ReverseDialog } from '@/components/documents'
import { Field } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Empty } from '@/components/reports'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDate, rupiah, today } from '@/lib/format'
import { cn } from '@/lib/utils'

import { AccountSelect } from './shared'

/** Bayar Hutang: pay a Supplier for owed Goods Receipts (rule 10). */
export function SupplierPaymentsPage() {
  const [params, setParams] = useSearchParams()
  const supplierId = params.get('pemasok') ?? ''
  const debts = useQuery(supplierPaymentsListDebtsOptions())
  const debt = debts.data?.find((d) => String(d.supplier_id) === supplierId)

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Bayar Hutang</h1>
      <p className="mt-1 text-muted-foreground">
        Bayar pemasok untuk barang masuk yang belum lunas. Tiap pembayaran tidak
        bisa melebihi sisa hutang barang masuknya.
      </p>
      {debts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(debts.error)}</p>
      )}
      {debts.data && debts.data.length === 0 && (
        <Empty>Tidak ada hutang ke pemasok.</Empty>
      )}
      {debts.data && debts.data.length > 0 && (
        <div className="mt-6 max-w-sm">
          <Select
            value={supplierId}
            onValueChange={(id) => setParams({ pemasok: id })}
          >
            <SelectTrigger className="w-full bg-card" aria-label="Pemasok">
              <SelectValue placeholder="Pilih pemasok" />
            </SelectTrigger>
            <SelectContent>
              {debts.data.map((d) => (
                <SelectItem key={d.supplier_id} value={String(d.supplier_id)}>
                  {d.supplier_name} · {rupiah(d.owed)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {debt && (
        <PaymentForm
          key={debt.supplier_id}
          supplierId={debt.supplier_id}
          receipts={debt.receipts}
        />
      )}
      <PaymentHistory />
    </>
  )
}

const rowKey = (row: OwedReceipt) => String(row.goods_receipt_id ?? 'awal')

function PaymentForm({
  supplierId,
  receipts,
}: {
  supplierId: number
  receipts: OwedReceipt[]
}) {
  const [paidOn, setPaidOn] = useState(today)
  const [paidFrom, setPaidFrom] = useState('')
  const [note, setNote] = useState('')
  // Digits to pay per receipt; empty means not paying it now.
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const chosen = receipts.filter((row) => Number(amounts[rowKey(row)] || 0))
  const total = chosen.reduce(
    (sum, row) => sum + Number(amounts[rowKey(row)]),
    0,
  )
  const pay = useMutation({
    ...supplierPaymentsCreatePaymentMutation(),
    onSuccess: (payment) => {
      queryClient.invalidateQueries()
      toast.success(
        `Pembayaran ${payment.number} ${rupiah(payment.amount)} dicatat.`,
      )
      setAmounts({})
    },
  })

  return (
    <section className="mt-4 rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Barang masuk</TableHead>
            <TableHead className="hidden text-right sm:table-cell">
              Sisa hutang
            </TableHead>
            <TableHead className="w-44 text-right">Bayar</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {receipts.map((row) => {
            const key = rowKey(row)
            const value = amounts[key] ?? ''
            const over = Number(value || 0) > row.owed
            return (
              <TableRow key={key}>
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
                      `total ${rupiah(row.total)}`,
                      row.returned ? `retur ${rupiah(row.returned)}` : null,
                      row.paid ? `dibayar ${rupiah(row.paid)}` : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                  <span className="block text-xs sm:hidden">
                    Sisa {rupiah(row.owed)}
                  </span>
                </TableCell>
                <TableCell className="hidden text-right whitespace-nowrap tabular-nums sm:table-cell">
                  {rupiah(row.owed)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <MoneyInput
                      aria-label={`Bayar ${row.number ?? 'saldo awal'}`}
                      value={value}
                      onValueChange={(digits) =>
                        setAmounts((current) => ({ ...current, [key]: digits }))
                      }
                      className={cn(over && 'border-destructive')}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setAmounts((current) => ({
                          ...current,
                          [key]: String(row.owed),
                        }))
                      }
                    >
                      Lunas
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <div className="grid gap-4 border-t p-4 sm:grid-cols-3">
        <Field id="pay-date" label="Tanggal bayar">
          <Input
            id="pay-date"
            type="date"
            value={paidOn}
            max={today()}
            onChange={(event) => setPaidOn(event.target.value)}
          />
        </Field>
        <Field id="pay-from" label="Dibayar dari">
          <AccountSelect
            id="pay-from"
            value={paidFrom}
            onChange={setPaidFrom}
            filter={(account) =>
              account.is_cash && account.role !== 'cash_drawer'
            }
            placeholder="Kas Besar"
          />
        </Field>
        <Field id="pay-note" label="Catatan (opsional)">
          <Input
            id="pay-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={300}
          />
        </Field>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t p-4">
        <p className="font-medium tabular-nums">Total bayar {rupiah(total)}</p>
        {pay.isError && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(pay.error)}
          </p>
        )}
        <Button
          disabled={total === 0 || pay.isPending}
          onClick={() =>
            pay.mutate({
              body: {
                supplier_id: supplierId,
                paid_on: paidOn,
                paid_from_account_id: paidFrom ? Number(paidFrom) : null,
                note: note || null,
                lines: chosen.map((row) => ({
                  goods_receipt_id: row.goods_receipt_id,
                  amount: Number(amounts[rowKey(row)]),
                })),
              },
            })
          }
        >
          {pay.isPending ? 'Menyimpan…' : 'Bayar'}
        </Button>
      </div>
    </section>
  )
}

function PaymentHistory() {
  const payments = useQuery({
    ...supplierPaymentsListPaymentsOptions({ query: { limit: 20 } }),
    placeholderData: keepPreviousData,
  })
  const [reversing, setReversing] = useState<SupplierPaymentPublic | null>(null)
  const reverse = useMutation({
    ...supplierPaymentsReversePaymentMutation(),
    onSuccess: (payment) => {
      queryClient.invalidateQueries()
      toast.success(`Pembayaran ${payment.number} dibatalkan.`)
      setReversing(null)
    },
  })
  if (!payments.data || payments.data.total === 0) return null
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold">Pembayaran terakhir</h2>
      <div className="mt-3 rounded-xl border bg-card">
        <Table>
          <TableBody>
            {payments.data.items.map((payment) => {
              const reversed = payment.status === 'reversed'
              return (
                <TableRow
                  key={payment.id}
                  className={cn(reversed && 'text-muted-foreground')}
                >
                  <TableCell>
                    <span className="font-medium tabular-nums">
                      {payment.number}
                    </span>
                    {reversed && (
                      <Badge variant="outline" className="ml-2">
                        Dibatalkan
                      </Badge>
                    )}
                    <span className="block text-xs text-muted-foreground">
                      {formatDate(payment.paid_on)} · {payment.supplier_name} ·
                      dari {payment.paid_from_name}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {payment.lines
                        .map(
                          (line) => line.goods_receipt_number ?? 'saldo awal',
                        )
                        .join(', ')}
                    </span>
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {rupiah(payment.amount)}
                  </TableCell>
                  <TableCell className="w-0">
                    {!reversed && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setReversing(payment)}
                      >
                        Batalkan
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {reversing && (
        <ReverseDialog
          title={`Batalkan pembayaran ${reversing.number}?`}
          description="Hutangnya kembali seperti sebelum dibayar; jurnalnya dibalik hari ini."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({
              path: { payment_id: reversing.id },
              body: { reason },
            })
          }
          onClose={() => setReversing(null)}
        />
      )}
    </section>
  )
}
