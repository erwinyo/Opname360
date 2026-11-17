import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ledgerReadAccountBookOptions } from '@/client/@tanstack/react-query.gen'
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
import { formatDate, money, today } from '@/lib/format'
import { ACCOUNT_TYPE_LABELS } from '@/lib/labels'

import { AccountSelect, Amount } from './shared'

/** Buku Besar: one account's entries with a running balance. */
export function AccountBookPage() {
  const [params, setParams] = useSearchParams()
  const accountId = params.get('akun') ?? ''
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const book = useQuery({
    ...ledgerReadAccountBookOptions({
      path: { account_id: Number(accountId) },
      query: { start, end },
    }),
    enabled: Boolean(accountId),
    placeholderData: keepPreviousData,
  })
  const data = book.data

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Buku Besar</h1>
      <p className="mt-1 text-muted-foreground">
        Semua jurnal satu akun dalam satu periode, dengan saldo berjalan.
      </p>
      <Filters>
        <div className="w-full sm:w-72">
          <AccountSelect
            value={accountId}
            onChange={(id) => setParams({ akun: id })}
            filter={() => true}
            label="Akun"
          />
        </div>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
      </Filters>
      {!accountId && <Empty>Pilih akunnya dulu.</Empty>}
      {book.isError && (
        <p className="mt-6 text-destructive">{errorMessage(book.error)}</p>
      )}
      {accountId && data && (
        <>
          <p className="mt-4 text-sm text-muted-foreground">
            {ACCOUNT_TYPE_LABELS[data.account.type]}. Saldo dihitung di sisi{' '}
            {['asset', 'cogs', 'expense'].includes(data.account.type)
              ? 'debit'
              : 'kredit'}
            ; angka minus berarti saldonya di sisi sebaliknya.
          </p>
          <div className="mt-2 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Jurnal</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">
                    Debit
                  </TableHead>
                  <TableHead className="hidden text-right sm:table-cell">
                    Kredit
                  </TableHead>
                  <TableHead className="text-right">Saldo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="text-muted-foreground">
                  <TableCell>Saldo awal {formatDate(data.start)}</TableCell>
                  <TableCell className="hidden sm:table-cell" />
                  <TableCell className="hidden sm:table-cell" />
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {money(data.opening_balance)}
                  </TableCell>
                </TableRow>
                {data.lines.map((line, index) => (
                  <TableRow key={`${line.entry_id}-${index}`}>
                    <TableCell>
                      <Link
                        to={`/jurnal/${line.entry_id}`}
                        className="font-medium tabular-nums"
                      >
                        {line.number}
                      </Link>
                      <span className="block text-xs text-muted-foreground">
                        {formatDate(line.entry_date)}
                      </span>
                      <span className="block text-sm">{line.description}</span>
                      <span className="block text-xs text-muted-foreground tabular-nums sm:hidden">
                        {Number(line.debit) > 0
                          ? `Debit ${money(line.debit)}`
                          : `Kredit ${money(line.credit)}`}
                      </span>
                    </TableCell>
                    <TableCell className="hidden text-right whitespace-nowrap tabular-nums sm:table-cell">
                      <Amount value={line.debit} />
                    </TableCell>
                    <TableCell className="hidden text-right whitespace-nowrap tabular-nums sm:table-cell">
                      <Amount value={line.credit} />
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(line.balance)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">
                    Saldo akhir {formatDate(data.end)}
                  </TableCell>
                  <TableCell className="hidden text-right font-semibold whitespace-nowrap tabular-nums sm:table-cell">
                    {money(data.total_debit)}
                  </TableCell>
                  <TableCell className="hidden text-right font-semibold whitespace-nowrap tabular-nums sm:table-cell">
                    {money(data.total_credit)}
                  </TableCell>
                  <TableCell className="text-right font-semibold whitespace-nowrap tabular-nums">
                    {money(data.closing_balance)}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </div>
        </>
      )}
    </>
  )
}
