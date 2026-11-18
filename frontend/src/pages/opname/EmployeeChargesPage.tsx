import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { ChargeStatus, EmployeeChargePublic } from '@/client'
import {
  employeeChargesListChargesOptions,
  employeeChargesSettleChargeMutation,
  employeeChargesOutstandingTotalsOptions,
} from '@/client/@tanstack/react-query.gen'
import { Field, FormDialog } from '@/components/FormDialog'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/format'
import { documentPath } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { AccountSelect } from '@/pages/ledger/shared'

const PAGE_SIZE = 50

const CHARGE_LABELS: Record<ChargeStatus, string> = {
  outstanding: 'Belum lunas',
  settled: 'Lunas',
  cancelled: 'Dibatalkan',
}

/** What employees owe for Shortages charged to them. */
export function EmployeeChargesPage() {
  const [settling, setSettling] = useState<EmployeeChargePublic | null>(null)
  const totals = useQuery(employeeChargesOutstandingTotalsOptions())
  const [userId, setUserId] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)
  const charges = useQuery({
    ...employeeChargesListChargesOptions({
      query: { user_id: userId, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const outstanding =
    totals.data?.reduce((sum, row) => sum + row.outstanding_amount, 0) ?? 0
  const pick = (id: number | null) => {
    setUserId(id)
    setOffset(0)
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">
        Ganti Rugi Karyawan
      </h1>
      <p className="mt-1 text-muted-foreground">
        Selisih kurang dari stok opname yang dibebankan ke karyawan.
        Pelunasannya dicatat di pembukuan nanti.
      </p>

      {totals.isError && (
        <p className="mt-6 text-destructive">{errorMessage(totals.error)}</p>
      )}
      <div className="mt-6 rounded-xl border bg-card p-4 sm:max-w-xs">
        <p className="text-sm text-muted-foreground">Total belum lunas</p>
        <p className="text-xl font-semibold tabular-nums">
          {rupiah(outstanding)}
        </p>
      </div>

      {totals.data && totals.data.length > 0 && (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {totals.data.map((row) => (
            <li key={row.user_id}>
              <button
                type="button"
                aria-pressed={userId === row.user_id}
                onClick={() =>
                  pick(userId === row.user_id ? null : row.user_id)
                }
                className={cn(
                  'flex w-full items-baseline justify-between gap-3 rounded-xl border bg-card p-4 text-left hover:border-primary/40',
                  userId === row.user_id && 'border-primary',
                )}
              >
                <span>
                  <span className="block font-medium">{row.full_name}</span>
                  <span className="block text-sm text-muted-foreground">
                    {row.outstanding_count} selisih
                  </span>
                </span>
                <span className="font-semibold tabular-nums">
                  {rupiah(row.outstanding_amount)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-8 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Riwayat</h2>
        {userId !== null && (
          <Button variant="ghost" size="sm" onClick={() => pick(null)}>
            Tampilkan semua karyawan
          </Button>
        )}
      </div>
      {charges.data?.total === 0 && (
        <p className="mt-3 rounded-xl border border-dashed p-6 text-muted-foreground">
          Belum ada ganti rugi karyawan.
        </p>
      )}
      {charges.data && charges.data.total > 0 && (
        <>
          <div className="mt-3 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Karyawan</TableHead>
                  <TableHead>Keterangan</TableHead>
                  <TableHead className="text-right">Jumlah</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {charges.data.items.map((charge) => {
                  const to = documentPath(charge.source_type, charge.source_id)
                  return (
                    <TableRow key={charge.id}>
                      <TableCell className="whitespace-nowrap">
                        {charge.user_name}
                        <span className="block text-sm text-muted-foreground">
                          {formatDateTime(charge.created_at)}
                        </span>
                      </TableCell>
                      <TableCell>
                        {charge.description}
                        {to && (
                          <Link
                            to={to}
                            className="block text-sm text-primary tabular-nums"
                          >
                            {charge.source_number}
                          </Link>
                        )}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {rupiah(charge.amount)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            charge.status === 'outstanding'
                              ? 'outline'
                              : 'secondary'
                          }
                        >
                          {CHARGE_LABELS[charge.status]}
                        </Badge>
                        {charge.status === 'settled' && (
                          <span className="block text-xs text-muted-foreground">
                            {charge.settled_by_salary
                              ? 'Potong gaji'
                              : 'Dibayar'}
                          </span>
                        )}
                        {charge.status === 'outstanding' && (
                          <Button
                            variant="link"
                            size="sm"
                            className="h-auto px-0"
                            onClick={() => setSettling(charge)}
                          >
                            Lunasi
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
            total={charges.data.total}
            unit="ganti rugi"
            onChange={setOffset}
          />
          {settling && (
            <SettleDialog charge={settling} onClose={() => setSettling(null)} />
          )}
        </>
      )}
    </>
  )
}

/** Paid back in cash, or deducted from salary. */
function SettleDialog({
  charge,
  onClose,
}: {
  charge: EmployeeChargePublic
  onClose: () => void
}) {
  const [bySalary, setBySalary] = useState(false)
  const [accountId, setAccountId] = useState('')
  const settle = useMutation({
    ...employeeChargesSettleChargeMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success(`Ganti rugi ${charge.user_name} lunas.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Lunasi ganti rugi ${charge.user_name}`}
      description={`${rupiah(charge.amount)}: ${charge.description}`}
      submitLabel="Lunasi"
      pending={settle.isPending}
      error={settle.error}
      onSubmit={() =>
        settle.mutate({
          path: { charge_id: charge.id },
          body: {
            by_salary: bySalary,
            account_id: !bySalary && accountId ? Number(accountId) : null,
          },
        })
      }
      onClose={onClose}
    >
      <fieldset className="grid gap-2">
        <legend className="sr-only">Cara melunasi</legend>
        {[false, true].map((salary) => (
          <label key={String(salary)} className="flex items-center gap-2.5">
            <input
              type="radio"
              name="settle"
              checked={bySalary === salary}
              onChange={() => setBySalary(salary)}
              className="size-4 accent-primary"
            />
            {salary ? 'Dipotong dari gaji' : 'Dibayar tunai atau transfer'}
          </label>
        ))}
      </fieldset>
      {!bySalary && (
        <Field id="settle-account" label="Uangnya masuk ke">
          <AccountSelect
            id="settle-account"
            value={accountId}
            onChange={setAccountId}
            filter={(account) =>
              account.is_cash && account.role !== 'cash_drawer'
            }
            placeholder="Kas Besar"
          />
        </Field>
      )}
    </FormDialog>
  )
}
