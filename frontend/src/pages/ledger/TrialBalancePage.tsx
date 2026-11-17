import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { ledgerTrialBalanceOptions } from '@/client/@tanstack/react-query.gen'
import { DateInput, Empty, Filters } from '@/components/reports'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { money, today } from '@/lib/format'

import { Amount } from './shared'

/** Neraca Saldo: every account's balance on a day; debit equals credit. */
export function TrialBalancePage() {
  const [on, setOn] = useState(today)
  const trial = useQuery({
    ...ledgerTrialBalanceOptions({ query: { on } }),
    placeholderData: keepPreviousData,
  })
  const data = trial.data
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Neraca Saldo</h1>
      <p className="mt-1 text-muted-foreground">
        Saldo setiap akun pada akhir hari yang dipilih. Jumlah debit selalu sama
        dengan jumlah kredit.
      </p>
      <Filters>
        <DateInput label="Per tanggal" value={on} onChange={setOn} />
      </Filters>
      {trial.isError && (
        <p className="mt-6 text-destructive">{errorMessage(trial.error)}</p>
      )}
      {data && data.rows.length === 0 && <Empty>Belum ada jurnal.</Empty>}
      {data && data.rows.length > 0 && (
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
              {data.rows.map((row) => (
                <TableRow key={row.account_id}>
                  <TableCell>
                    <Link to={`/buku-besar?akun=${row.account_id}`}>
                      <span className="tabular-nums">{row.code}</span>{' '}
                      {row.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    <Amount value={row.debit} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    <Amount value={row.credit} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell className="font-semibold">Jumlah</TableCell>
                <TableCell className="text-right font-semibold whitespace-nowrap tabular-nums">
                  {money(data.total_debit)}
                </TableCell>
                <TableCell className="text-right font-semibold whitespace-nowrap tabular-nums">
                  {money(data.total_credit)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>
      )}
    </>
  )
}
