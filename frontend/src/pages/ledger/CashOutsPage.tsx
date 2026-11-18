import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { CashOutPublic } from '@/client'
import {
  cashCreateCashOutMutation,
  cashListCashOutsOptions,
  cashReverseCashOutMutation,
} from '@/client/@tanstack/react-query.gen'
import { ReverseDialog } from '@/components/documents'
import { Field, FormDialog } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Pager } from '@/components/Pager'
import { DateInput, Empty, Filters } from '@/components/reports'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

const PAGE_SIZE = 50
// Moved only by their documents.
const NOT_EXPENSES = [
  'inventory',
  'cash_drawer',
  'accounts_payable',
  'employee_receivable',
  'opening_balance',
]

/** Kas Keluar: expenses paid from a cash or bank account. */
export function CashOutsPage() {
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const [reversing, setReversing] = useState<CashOutPublic | null>(null)
  const list = useQuery({
    ...cashListCashOutsOptions({
      query: { start, end, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const reverse = useMutation({
    ...cashReverseCashOutMutation(),
    onSuccess: (cashOut) => {
      queryClient.invalidateQueries()
      toast.success(`Kas keluar ${cashOut.number} dibatalkan.`)
      setReversing(null)
    },
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Kas Keluar</h1>
          <p className="mt-1 text-muted-foreground">
            Biaya yang dibayar dari kas atau bank. Dari laci kasir hanya saat
            shift berjalan, dan mengurangi kas yang seharusnya ada.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <PlusIcon />
          Catat kas keluar
        </Button>
      </div>
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
      </Filters>
      {list.isError && (
        <p className="mt-6 text-destructive">{errorMessage(list.error)}</p>
      )}
      {list.data && list.data.total === 0 && (
        <Empty>Belum ada kas keluar dalam periode ini.</Empty>
      )}
      {list.data && list.data.total > 0 && (
        <>
          <div className="mt-4 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Kas keluar</TableHead>
                  <TableHead className="hidden md:table-cell">Akun</TableHead>
                  <TableHead className="text-right">Jumlah</TableHead>
                  <TableHead className="w-0">
                    <span className="sr-only">Tindakan</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.items.map((item) => {
                  const reversed = item.status === 'reversed'
                  return (
                    <TableRow
                      key={item.id}
                      className={cn(reversed && 'text-muted-foreground')}
                    >
                      <TableCell>
                        <span className="font-medium tabular-nums">
                          {item.number}
                        </span>
                        {reversed && (
                          <Badge variant="outline" className="ml-2">
                            Dibatalkan
                          </Badge>
                        )}
                        <span className="block text-xs text-muted-foreground">
                          {formatDate(item.paid_on)}
                          {item.paid_to && ` · ${item.paid_to}`}
                          {item.shift_number && ` · shift ${item.shift_number}`}
                        </span>
                        <span className="block text-sm">
                          {item.description}
                        </span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {item.expense_name}
                        <span className="block text-xs text-muted-foreground">
                          dari {item.paid_from_name}
                        </span>
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {rupiah(item.amount)}
                      </TableCell>
                      <TableCell>
                        {!reversed && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setReversing(item)}
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
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={list.data.total}
            unit="kas keluar"
            onChange={setOffset}
          />
        </>
      )}
      {creating && <CashOutDialog onClose={() => setCreating(false)} />}
      {reversing && (
        <ReverseDialog
          title={`Batalkan kas keluar ${reversing.number}?`}
          description="Jurnalnya dibalik dengan tanggal hari ini."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({
              path: { cash_out_id: reversing.id },
              body: { reason },
            })
          }
          onClose={() => setReversing(null)}
        />
      )}
    </>
  )
}

function CashOutDialog({ onClose }: { onClose: () => void }) {
  const [paidOn, setPaidOn] = useState(today)
  const [paidFrom, setPaidFrom] = useState('')
  const [expense, setExpense] = useState('')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [paidTo, setPaidTo] = useState('')
  const [checked, setChecked] = useState(false)
  const problem = !paidFrom
    ? 'Pilih dari mana dibayar.'
    : !expense
      ? 'Pilih akun biayanya.'
      : !Number(amount)
        ? 'Isi jumlahnya.'
        : !description.trim()
          ? 'Isi keterangannya.'
          : undefined
  const create = useMutation({
    ...cashCreateCashOutMutation(),
    onSuccess: (cashOut) => {
      queryClient.invalidateQueries()
      toast.success(`Kas keluar ${cashOut.number} dicatat.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title="Catat kas keluar"
      submitLabel="Simpan"
      pending={create.isPending}
      error={create.error ?? (checked ? problem : null)}
      onSubmit={() => {
        setChecked(true)
        if (problem) return
        create.mutate({
          body: {
            paid_on: paidOn,
            paid_from_account_id: Number(paidFrom),
            expense_account_id: Number(expense),
            amount: Number(amount),
            description,
            paid_to: paidTo || null,
          },
        })
      }}
      onClose={onClose}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="cash-out-date" label="Tanggal">
          <Input
            id="cash-out-date"
            type="date"
            value={paidOn}
            max={today()}
            onChange={(event) => setPaidOn(event.target.value)}
          />
        </Field>
        <Field id="cash-out-amount" label="Jumlah">
          <MoneyInput
            id="cash-out-amount"
            value={amount}
            onValueChange={setAmount}
          />
        </Field>
      </div>
      <Field id="cash-out-from" label="Dibayar dari">
        <AccountSelect
          id="cash-out-from"
          value={paidFrom}
          onChange={setPaidFrom}
          filter={(account) => account.is_cash}
        />
      </Field>
      <Field id="cash-out-expense" label="Untuk (akun biaya)">
        <AccountSelect
          id="cash-out-expense"
          value={expense}
          onChange={setExpense}
          filter={(account) =>
            !account.is_cash &&
            (!account.role || !NOT_EXPENSES.includes(account.role))
          }
        />
      </Field>
      <Field id="cash-out-description" label="Keterangan">
        <Input
          id="cash-out-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={300}
        />
      </Field>
      <Field id="cash-out-to" label="Dibayar kepada (opsional)">
        <Input
          id="cash-out-to"
          value={paidTo}
          onChange={(event) => setPaidTo(event.target.value)}
          maxLength={100}
        />
      </Field>
    </FormDialog>
  )
}
