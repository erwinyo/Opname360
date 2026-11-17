import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { shiftsListShiftsOptions } from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/format'

import { CashVariance, ShiftDecision } from './shiftParts'

const PAGE_SIZE = 50

/** Every Shift with its Cash Variance; shortages wait for the Owner. */
export function ShiftsPage() {
  // The dashboard links here with ?menunggu=1.
  const [waiting, setWaiting] = useState(
    () => new URLSearchParams(window.location.search).get('menunggu') === '1',
  )
  const [offset, setOffset] = useState(0)
  const shifts = useQuery({
    ...shiftsListShiftsOptions({
      query: { needs_resolution: waiting, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Shift</h1>
      <p className="mt-1 text-muted-foreground">
        Setiap shift kasir dan hasil hitung kasnya. Kas yang kurang menunggu
        keputusan Pemilik: kerugian perusahaan atau ganti rugi karyawan.
      </p>
      <div className="mt-6 flex items-center gap-3">
        <Switch
          id="waiting"
          checked={waiting}
          onCheckedChange={(checked) => {
            setWaiting(checked)
            setOffset(0)
          }}
        />
        <Label htmlFor="waiting">Hanya yang menunggu keputusan</Label>
      </div>

      {shifts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(shifts.error)}</p>
      )}
      {shifts.data?.total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {waiting ? 'Tidak ada yang menunggu keputusan.' : 'Belum ada shift.'}
        </p>
      )}
      {shifts.data && shifts.data.total > 0 && (
        <>
          <div className="mt-4 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Shift</TableHead>
                  <TableHead>Kasir</TableHead>
                  <TableHead>Dibuka</TableHead>
                  <TableHead className="text-right">Penjualan bersih</TableHead>
                  <TableHead>Kas</TableHead>
                  <TableHead>Keputusan</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shifts.data.items.map((shift) => (
                  <TableRow key={shift.id}>
                    <TableCell>
                      <Link
                        to={`/shift/${shift.id}`}
                        className="font-medium text-primary tabular-nums hover:underline"
                      >
                        {shift.number}
                      </Link>
                    </TableCell>
                    <TableCell>{shift.cashier_name}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(shift.opened_at)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {rupiah(shift.net_sales)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <CashVariance shift={shift} />
                    </TableCell>
                    <TableCell>
                      <ShiftDecision shift={shift} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={shifts.data.total}
            unit="shift"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
