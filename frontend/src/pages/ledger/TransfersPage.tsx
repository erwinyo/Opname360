import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { AccountPublic, CashTransferPublic } from '@/client'
import {
  cashCreateTransferMutation,
  cashListTransfersOptions,
  cashReverseTransferMutation,
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
// The drawer fills and empties only with its Shift.
const movable = (account: AccountPublic) =>
  account.is_cash && account.role !== 'cash_drawer'

/** Pindah Kas: e.g. depositing Kas Besar at the bank. */
export function TransfersPage() {
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const [reversing, setReversing] = useState<CashTransferPublic | null>(null)
  const list = useQuery({
    ...cashListTransfersOptions({
      query: { start, end, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const reverse = useMutation({
    ...cashReverseTransferMutation(),
    onSuccess: (transfer) => {
      queryClient.invalidateQueries()
      toast.success(`Pindah kas ${transfer.number} dibatalkan.`)
      setReversing(null)
    },
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pindah Kas</h1>
          <p className="mt-1 text-muted-foreground">
            Uang pindah antar akun kas dan bank, misalnya setor kas besar ke
            bank.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <PlusIcon />
          Catat pindah kas
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
        <Empty>Belum ada pindah kas dalam periode ini.</Empty>
      )}
      {list.data && list.data.total > 0 && (
        <>
          <div className="mt-4 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pindah kas</TableHead>
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
                          {formatDate(item.transferred_on)}
                        </span>
                        <span className="block text-sm">
                          {item.from_name} → {item.to_name}
                          {item.description && ` · ${item.description}`}
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
            unit="pindah kas"
            onChange={setOffset}
          />
        </>
      )}
      {creating && <TransferDialog onClose={() => setCreating(false)} />}
      {reversing && (
        <ReverseDialog
          title={`Batalkan pindah kas ${reversing.number}?`}
          description="Jurnalnya dibalik dengan tanggal hari ini."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({
              path: { transfer_id: reversing.id },
              body: { reason },
            })
          }
          onClose={() => setReversing(null)}
        />
      )}
    </>
  )
}

function TransferDialog({ onClose }: { onClose: () => void }) {
  const [day, setDay] = useState(today)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [checked, setChecked] = useState(false)
  const problem =
    !from || !to
      ? 'Pilih akun asal dan tujuan.'
      : from === to
        ? 'Pilih dua akun yang berbeda.'
        : !Number(amount)
          ? 'Isi jumlahnya.'
          : undefined
  const create = useMutation({
    ...cashCreateTransferMutation(),
    onSuccess: (transfer) => {
      queryClient.invalidateQueries()
      toast.success(`Pindah kas ${transfer.number} dicatat.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title="Catat pindah kas"
      submitLabel="Simpan"
      pending={create.isPending}
      error={create.error ?? (checked ? problem : null)}
      onSubmit={() => {
        setChecked(true)
        if (problem) return
        create.mutate({
          body: {
            transferred_on: day,
            from_account_id: Number(from),
            to_account_id: Number(to),
            amount: Number(amount),
            description: description || null,
          },
        })
      }}
      onClose={onClose}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="transfer-date" label="Tanggal">
          <Input
            id="transfer-date"
            type="date"
            value={day}
            max={today()}
            onChange={(event) => setDay(event.target.value)}
          />
        </Field>
        <Field id="transfer-amount" label="Jumlah">
          <MoneyInput
            id="transfer-amount"
            value={amount}
            onValueChange={setAmount}
          />
        </Field>
      </div>
      <Field id="transfer-from" label="Dari">
        <AccountSelect
          id="transfer-from"
          value={from}
          onChange={setFrom}
          filter={movable}
        />
      </Field>
      <Field id="transfer-to" label="Ke">
        <AccountSelect
          id="transfer-to"
          value={to}
          onChange={setTo}
          filter={movable}
        />
      </Field>
      <Field id="transfer-description" label="Keterangan (opsional)">
        <Input
          id="transfer-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={300}
        />
      </Field>
    </FormDialog>
  )
}
