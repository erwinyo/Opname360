import { useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { AccountPublic } from '@/client'
import {
  ledgerEnterOpeningBalancesMutation,
  ledgerListAccountsOptions,
  ledgerReadOpeningBalancesOptions,
  suppliersListSuppliersOptions,
} from '@/client/@tanstack/react-query.gen'
import { Field } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
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

import { AccountSelect, Amount } from './shared'

// Stock comes from the Opening Opname; the drawer, charges and Saldo Awal
// itself from their own records.
const NOT_HERE = [
  'inventory',
  'cash_drawer',
  'employee_receivable',
  'opening_balance',
]

type Line = {
  key: number
  accountId: string
  supplierId: string
  debit: string
  credit: string
}
let nextKey = 0
const emptyLine = (): Line => ({
  key: nextKey++,
  accountId: '',
  supplierId: '',
  debit: '',
  credit: '',
})

/** Saldo Awal (Owner): cash, bank, debts and capital on the day the books
 *  start, entered once (rule 11). */
export function OpeningBalancesPage() {
  const opening = useQuery(ledgerReadOpeningBalancesOptions())
  if (opening.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (opening.isError) {
    return <p className="text-destructive">{errorMessage(opening.error)}</p>
  }
  const entry = opening.data
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Saldo Awal</h1>
      <p className="mt-1 text-muted-foreground">
        Saldo kas, bank, hutang ke pemasok, dan modal pada hari pembukuan
        dimulai. Diisi sekali; stok awal berasal dari opname awal.
      </p>
      {entry ? (
        <>
          <p className="mt-6">
            Sudah diisi per {formatDate(entry.entry_date)} dengan jurnal{' '}
            <Link to={`/jurnal/${entry.id}`} className="text-primary underline">
              {entry.number}
            </Link>
            . Untuk mengubahnya, batalkan jurnal itu lalu isi lagi.
          </p>
          <div className="mt-4 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Akun</TableHead>
                  <TableHead className="text-right">Debit</TableHead>
                  <TableHead className="text-right">Kredit</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entry.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>
                      {line.account_code} {line.account_name}
                      {line.supplier_name && (
                        <span className="block text-xs text-muted-foreground">
                          {line.supplier_name}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Amount value={line.debit} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <Amount value={line.credit} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      ) : (
        <OpeningForm />
      )}
    </>
  )
}

function OpeningForm() {
  const accounts = useQuery(ledgerListAccountsOptions())
  const suppliers = useQuery(suppliersListSuppliersOptions())
  const [entryDate, setEntryDate] = useState(today)
  const [lines, setLines] = useState<Line[]>(() => [emptyLine(), emptyLine()])
  const [checked, setChecked] = useState(false)
  const payable = (id: string) =>
    accounts.data?.find((a) => String(a.id) === id)?.role === 'accounts_payable'
  const filled = lines.filter((l) => l.accountId && (l.debit || l.credit))
  const difference = filled.reduce(
    (sum, l) => sum + Number(l.debit || 0) - Number(l.credit || 0),
    0,
  )
  const problem =
    filled.length === 0
      ? 'Isi minimal satu saldo.'
      : filled.some((l) => payable(l.accountId) && !l.supplierId)
        ? 'Hutang usaha harus menyebut pemasoknya.'
        : undefined
  const save = useMutation({
    ...ledgerEnterOpeningBalancesMutation(),
    onSuccess: (entry) => {
      queryClient.invalidateQueries()
      toast.success(`Saldo awal disimpan (${entry.number}).`)
    },
  })
  const change = (key: number, patch: Partial<Line>) =>
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  const usable = (account: AccountPublic) =>
    !account.role || !NOT_HERE.includes(account.role)

  return (
    <div className="mt-6 grid gap-4">
      <div className="max-w-48">
        <Field id="opening-date" label="Tanggal mulai pembukuan">
          <Input
            id="opening-date"
            type="date"
            value={entryDate}
            max={today()}
            onChange={(event) => setEntryDate(event.target.value)}
          />
        </Field>
      </div>
      <div className="grid gap-3 rounded-xl border bg-card p-4">
        {lines.map((line, index) => (
          <div
            key={line.key}
            className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_10rem_10rem_2.5rem]"
          >
            <div className="col-span-2 grid gap-2 sm:col-span-1">
              <AccountSelect
                value={line.accountId}
                onChange={(accountId) => change(line.key, { accountId })}
                filter={usable}
                label={`Akun baris ${index + 1}`}
              />
              {payable(line.accountId) && (
                <Select
                  value={line.supplierId}
                  onValueChange={(supplierId) =>
                    change(line.key, { supplierId })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={`Pemasok baris ${index + 1}`}
                  >
                    <SelectValue placeholder="Pilih pemasok" />
                  </SelectTrigger>
                  <SelectContent>
                    {suppliers.data?.map((supplier) => (
                      <SelectItem key={supplier.id} value={String(supplier.id)}>
                        {supplier.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <MoneyInput
              aria-label={`Debit baris ${index + 1}`}
              placeholder="Debit"
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
              placeholder="Kredit"
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
              disabled={lines.length <= 1}
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
        <p className="border-t pt-3 text-sm">
          Saldo Awal (ekuitas) otomatis{' '}
          <span className="font-medium tabular-nums">
            {difference >= 0 ? 'kredit' : 'debit'}{' '}
            {rupiah(Math.abs(difference))}
          </span>
          .
        </p>
      </div>
      {checked && problem && (
        <p role="alert" className="text-sm text-destructive">
          {problem}
        </p>
      )}
      {save.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
      <div>
        <Button
          disabled={save.isPending}
          onClick={() => {
            setChecked(true)
            if (problem) return
            save.mutate({
              body: {
                entry_date: entryDate,
                lines: filled.map((line) => ({
                  account_id: Number(line.accountId),
                  debit: line.debit || 0,
                  credit: line.credit || 0,
                  supplier_id: line.supplierId ? Number(line.supplierId) : null,
                })),
              },
            })
          }}
        >
          {save.isPending ? 'Menyimpan…' : 'Simpan saldo awal'}
        </Button>
      </div>
    </div>
  )
}
