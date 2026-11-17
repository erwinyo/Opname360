import { useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import type { AccountPublic } from '@/client'
import {
  ledgerCreateManualEntryMutation,
  ledgerListAccountsOptions,
} from '@/client/@tanstack/react-query.gen'
import { BackLink } from '@/components/documents'
import { Field } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { rupiah, today } from '@/lib/format'
import { cn } from '@/lib/utils'

import { AccountSelect } from './shared'

// Moved only by their documents, so their balances stay true.
const SYSTEM_ONLY = [
  'inventory',
  'cash_drawer',
  'accounts_payable',
  'employee_receivable',
  'opening_balance',
]

type Line = { key: number; accountId: string; debit: string; credit: string }

let nextKey = 0
const emptyLine = (): Line => ({
  key: nextKey++,
  accountId: '',
  debit: '',
  credit: '',
})

/** Jurnal Umum: capital, withdrawals, depreciation and anything else. */
export function ManualEntryPage() {
  const navigate = useNavigate()
  useQuery(ledgerListAccountsOptions())
  const [entryDate, setEntryDate] = useState(today)
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<Line[]>(() => [emptyLine(), emptyLine()])
  const [checked, setChecked] = useState(false)
  const debit = lines.reduce((sum, line) => sum + Number(line.debit || 0), 0)
  const credit = lines.reduce((sum, line) => sum + Number(line.credit || 0), 0)
  const filled = lines.filter(
    (line) => line.accountId && (line.debit || line.credit),
  )
  const problem = !description.trim()
    ? 'Isi keterangannya.'
    : filled.length < 2
      ? 'Isi minimal dua baris.'
      : debit !== credit
        ? `Debit dan kredit belum seimbang: selisih ${rupiah(Math.abs(debit - credit))}.`
        : undefined
  const create = useMutation({
    ...ledgerCreateManualEntryMutation(),
    onSuccess: (entry) => {
      toast.success(`Jurnal ${entry.number} disimpan.`)
      navigate(`/jurnal/${entry.id}`)
    },
  })
  const change = (key: number, patch: Partial<Line>) =>
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (problem) return
    create.mutate({
      body: {
        entry_date: entryDate,
        description,
        lines: filled.map((line) => ({
          account_id: Number(line.accountId),
          debit: line.debit || 0,
          credit: line.credit || 0,
        })),
      },
    })
  }
  const usable = (account: AccountPublic) =>
    !account.role || !SYSTEM_ONLY.includes(account.role)

  return (
    <form onSubmit={submit} noValidate>
      <BackLink to="/jurnal" label="Jurnal" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        Jurnal umum
      </h1>
      <p className="mt-1 text-muted-foreground">
        Untuk yang tidak tercatat lewat dokumen: setoran modal, prive,
        penyusutan, dan lainnya. Persediaan, kas kasir, hutang usaha, dan
        piutang karyawan hanya berubah lewat dokumennya.
      </p>
      <div className="mt-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-[12rem_1fr]">
        <Field id="entry-date" label="Tanggal">
          <Input
            id="entry-date"
            type="date"
            value={entryDate}
            max={today()}
            onChange={(event) => setEntryDate(event.target.value)}
          />
        </Field>
        <Field id="entry-description" label="Keterangan">
          <Input
            id="entry-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={300}
          />
        </Field>
      </div>
      <div className="mt-4 grid gap-3 rounded-xl border bg-card p-4">
        <div className="hidden grid-cols-[1fr_10rem_10rem_2.5rem] gap-2 text-sm text-muted-foreground sm:grid">
          <span>Akun</span>
          <span className="text-right">Debit</span>
          <span className="text-right">Kredit</span>
        </div>
        {lines.map((line, index) => (
          <div
            key={line.key}
            className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_10rem_10rem_2.5rem]"
          >
            <div className="col-span-2 sm:col-span-1">
              <AccountSelect
                value={line.accountId}
                onChange={(accountId) => change(line.key, { accountId })}
                filter={usable}
                label={`Akun baris ${index + 1}`}
              />
            </div>
            <MoneyInput
              aria-label={`Debit baris ${index + 1}`}
              value={line.debit}
              onValueChange={(digits) =>
                change(line.key, {
                  debit: digits,
                  credit: digits ? '' : line.credit,
                })
              }
            />
            <MoneyInput
              aria-label={`Kredit baris ${index + 1}`}
              value={line.credit}
              onValueChange={(digits) =>
                change(line.key, {
                  credit: digits,
                  debit: digits ? '' : line.debit,
                })
              }
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Hapus baris ${index + 1}`}
              disabled={lines.length <= 2}
              onClick={() =>
                setLines((current) => current.filter((l) => l.key !== line.key))
              }
            >
              <Trash2Icon />
            </Button>
          </div>
        ))}
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setLines((current) => [...current, emptyLine()])}
          >
            <PlusIcon />
            Tambah baris
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 border-t pt-3 font-medium tabular-nums sm:grid-cols-[1fr_10rem_10rem_2.5rem]">
          <span className="hidden sm:block">Jumlah</span>
          <span className="text-right">{rupiah(debit)}</span>
          <span
            className={cn('text-right', debit !== credit && 'text-destructive')}
          >
            {rupiah(credit)}
          </span>
        </div>
      </div>
      {checked && problem && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {problem}
        </p>
      )}
      {create.isError && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {errorMessage(create.error)}
        </p>
      )}
      <Button type="submit" className="mt-4" disabled={create.isPending}>
        {create.isPending ? 'Menyimpan…' : 'Simpan jurnal'}
      </Button>
    </form>
  )
}
