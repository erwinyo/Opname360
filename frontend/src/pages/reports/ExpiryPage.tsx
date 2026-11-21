import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ClipboardCheckIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { ExpiryRow } from '@/client'
import { reportsExpiryOptions } from '@/client/@tanstack/react-query.gen'
import { Empty, Filters, ReportHeader } from '@/components/reports'
import { Button } from '@/components/ui/button'
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
import { errorMessage } from '@/lib/api'
import { formatDate, money, quantity, skuName, today } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { OpnameFromReport } from '@/pages/opname/OpenOpnamePage'

const WINDOWS = ['30', '60', '90']
const DAY = 86_400_000

/** "lewat 3 hari", "hari ini", "12 hari lagi" */
function untilExpiry(isoDate: string): string {
  const left = Math.round(
    (new Date(`${isoDate}T00:00:00`).getTime() -
      new Date(`${today()}T00:00:00`).getTime()) /
      DAY,
  )
  if (left < 0) return `lewat ${-left} hari`
  if (left === 0) return 'hari ini'
  return `${left} hari lagi`
}

/** Slice 6, rule 15: medicine that has expired or soon will. */
export function ExpiryPage() {
  const navigate = useNavigate()
  const [days, setDays] = useState('90')
  const report = useQuery({
    ...reportsExpiryOptions({ query: { days: Number(days) } }),
    placeholderData: keepPreviousData,
  })
  const data = report.data
  const rows = data?.rows ?? []
  const expired = rows.filter((row) => row.expired)
  const expiring = rows.filter((row) => !row.expired)

  // Rule 14: expired stock is written off by a Partial Opname.
  const writeOff = () => {
    const skus = new Map(
      expired.map((row) => [row.sku_id, { ...row, id: row.sku_id }]),
    )
    const state: OpnameFromReport = {
      skus: [...skus.values()],
      note: 'Batch kedaluwarsa diturunkan dari rak',
    }
    navigate('/stok-opname/baru', { state })
  }

  return (
    <>
      <ReportHeader
        title="Kedaluwarsa"
        description="Batch yang masih ada stoknya dan sudah lewat atau mendekati tanggal kedaluwarsa, dinilai dengan HPP rata-rata barangnya."
      />
      <Filters>
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="bg-card" aria-label="Kedaluwarsa dalam">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WINDOWS.map((window) => (
              <SelectItem key={window} value={window}>
                Dalam {window} hari
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Filters>
      {report.isError && (
        <p className="mt-6 text-destructive">{errorMessage(report.error)}</p>
      )}
      {data && rows.length === 0 && (
        <Empty>
          Tidak ada batch yang sudah atau akan kedaluwarsa dalam {days} hari.
        </Empty>
      )}
      {data && expired.length > 0 && (
        <section className="mt-6">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="font-medium text-destructive">
                Sudah kedaluwarsa
              </h2>
              <p className="text-sm text-muted-foreground tabular-nums">
                {expired.length} batch · {money(data.expired_value)}. Turunkan
                dari rak, lalu opname untuk mengeluarkannya dari stok.
              </p>
            </div>
            <Button variant="outline" onClick={writeOff}>
              <ClipboardCheckIcon />
              Opname barang ini
            </Button>
          </div>
          <BatchTable rows={expired} />
        </section>
      )}
      {data && expiring.length > 0 && (
        <section className="mt-8">
          <h2 className="font-medium">Kedaluwarsa dalam {data.days} hari</h2>
          <p className="text-sm text-muted-foreground tabular-nums">
            {expiring.length} batch · {money(data.expiring_value)}
          </p>
          <BatchTable rows={expiring} />
        </section>
      )}
    </>
  )
}

function BatchTable({ rows }: { rows: ExpiryRow[] }) {
  return (
    <div className="mt-2 rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Barang</TableHead>
            <TableHead>Batch</TableHead>
            <TableHead>Kedaluwarsa</TableHead>
            <TableHead className="text-right">Jumlah</TableHead>
            <TableHead className="text-right">Nilai</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.batch_id}>
              <TableCell>
                <Link to={`/stok/${row.sku_id}`} className="font-medium">
                  {skuName(row)}
                </Link>
                <span className="block text-xs text-muted-foreground">
                  {row.code}
                </span>
              </TableCell>
              <TableCell className="tabular-nums">{row.batch_number}</TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">
                {formatDate(row.expires_on)}
                <span
                  className={cn(
                    'block text-xs',
                    row.expired ? 'text-destructive' : 'text-muted-foreground',
                  )}
                >
                  {untilExpiry(row.expires_on)}
                </span>
              </TableCell>
              <TableCell className="text-right whitespace-nowrap tabular-nums">
                {quantity(row.quantity)} {row.stock_unit}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {money(row.value)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
