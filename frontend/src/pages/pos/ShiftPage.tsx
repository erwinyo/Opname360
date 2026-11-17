import { useQuery } from '@tanstack/react-query'
import { PrinterIcon } from 'lucide-react'
import { useParams } from 'react-router'

import type { ShiftPublic, UserPublic } from '@/client'
import { shiftsReadShiftOptions } from '@/client/@tanstack/react-query.gen'
import { BackLink, Facts } from '@/components/documents'
import { SlipRow, ThermalPrint } from '@/components/ThermalPrint'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/format'
import { cn } from '@/lib/utils'

/** A Shift's closing summary; while open, only the back office sees it. */
export function ShiftPage({ user }: { user: UserPublic }) {
  const shiftId = Number(useParams().shiftId)
  const shift = useQuery(
    shiftsReadShiftOptions({ path: { shift_id: shiftId } }),
  )
  const back =
    user.role === 'cashier' ? (
      <BackLink to="/kasir" label="Kasir" />
    ) : (
      <BackLink to="/shift" label="Shift" />
    )

  if (shift.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (shift.isError) {
    return (
      <>
        {back}
        <p className="mt-4 text-destructive">{errorMessage(shift.error)}</p>
      </>
    )
  }
  const data = shift.data
  return (
    <>
      {back}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          Shift {data.number}
        </h1>
        {data.closed_at && (
          <Button variant="outline" onClick={() => window.print()}>
            <PrinterIcon />
            Cetak ringkasan
          </Button>
        )}
      </div>
      <Facts
        facts={[
          ['Kasir', data.cashier_name],
          ['Dibuka', formatDateTime(data.opened_at)],
          [
            'Ditutup',
            data.closed_at
              ? `${formatDateTime(data.closed_at)} oleh ${data.closed_by_name}`
              : 'Masih terbuka',
          ],
        ]}
      />
      <CashCount shift={data} />
      {data.closed_at && (
        <ThermalPrint>
          <ShiftSlip shift={data} />
        </ThermalPrint>
      )}
    </>
  )
}

function CashCount({ shift }: { shift: ShiftPublic }) {
  const variance = shift.cash_variance
  return (
    <section className="mt-4 max-w-md rounded-xl border bg-card p-4">
      <h2 className="font-medium">Kas di laci</h2>
      <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 tabular-nums">
        <dt className="text-muted-foreground">Modal kas</dt>
        <dd className="text-right">{rupiah(shift.opening_float)}</dd>
        <dt className="text-muted-foreground">
          {shift.closed_at ? 'Seharusnya' : 'Seharusnya saat ini'}
        </dt>
        <dd className="text-right">{rupiah(shift.expected_cash)}</dd>
        {shift.counted_cash != null && (
          <>
            <dt className="text-muted-foreground">Dihitung</dt>
            <dd className="text-right">{rupiah(shift.counted_cash)}</dd>
          </>
        )}
        {variance != null && (
          <>
            <dt className="font-medium">Selisih</dt>
            <dd
              className={cn(
                'text-right font-semibold',
                variance < 0 && 'text-destructive',
              )}
            >
              {variance === 0
                ? 'Sesuai'
                : `${variance > 0 ? 'Lebih' : 'Kurang'} ${rupiah(Math.abs(variance))}`}
            </dd>
          </>
        )}
      </dl>
    </section>
  )
}

function ShiftSlip({ shift }: { shift: ShiftPublic }) {
  return (
    <>
      <p className="text-center font-bold">RINGKASAN SHIFT</p>
      <p className="text-center">{shift.number}</p>
      <p className="mt-2">Kasir: {shift.cashier_name}</p>
      <p>Buka : {formatDateTime(shift.opened_at)}</p>
      {shift.closed_at && <p>Tutup: {formatDateTime(shift.closed_at)}</p>}
      <div className="my-2 border-t border-dashed border-black" />
      <SlipRow label="Modal kas" value={rupiah(shift.opening_float)} />
      <SlipRow label="Kas seharusnya" value={rupiah(shift.expected_cash)} />
      <SlipRow label="Kas dihitung" value={rupiah(shift.counted_cash ?? 0)} />
      <SlipRow label="Selisih" value={rupiah(shift.cash_variance ?? 0)} bold />
      <div className="mt-10 grid grid-cols-2 gap-4 text-center">
        <p className="border-t border-black pt-1">Kasir</p>
        <p className="border-t border-black pt-1">Penerima</p>
      </div>
    </>
  )
}
