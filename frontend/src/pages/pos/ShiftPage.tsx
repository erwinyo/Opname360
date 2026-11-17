import { useMutation, useQuery } from '@tanstack/react-query'
import { PrinterIcon } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router'
import { toast } from 'sonner'

import type { Resolution, ShiftPublic, UserPublic } from '@/client'
import {
  opnamesListStaffOptions,
  shiftsListShiftsQueryKey,
  shiftsReadShiftOptions,
  shiftsReadShiftQueryKey,
  shiftsResolveShiftMutation,
} from '@/client/@tanstack/react-query.gen'
import { BackLink, Facts } from '@/components/documents'
import { Field } from '@/components/FormDialog'
import { SlipRow, ThermalPrint } from '@/components/ThermalPrint'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/format'
import { RESOLUTION_LABELS } from '@/lib/labels'

import { ReceiptList } from './ReceiptList'
import { CashVariance, ShiftDecision } from './shiftParts'

/** A Shift's closing summary; while open, only the back office sees it. */
export function ShiftPage({ user }: { user: UserPublic }) {
  const shiftId = Number(useParams().shiftId)
  const shift = useQuery(
    shiftsReadShiftOptions({ path: { shift_id: shiftId } }),
  )
  const backOffice = user.role !== 'cashier'
  const back = backOffice ? (
    <BackLink to="/shift" label="Shift" />
  ) : (
    <BackLink to="/kasir" label="Kasir" />
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
      <div className="mt-4 grid items-start gap-4 md:grid-cols-2">
        <CashCount shift={data} />
        <Takings shift={data} />
      </div>
      {data.needs_resolution && user.role === 'owner' && (
        <ResolveShortage shift={data} />
      )}
      {backOffice && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-semibold">Transaksi</h2>
          <ReceiptList shiftId={data.id} actions={false} />
        </section>
      )}
      {data.closed_at && (
        <ThermalPrint>
          <ShiftSlip shift={data} />
        </ThermalPrint>
      )}
    </>
  )
}

function CashCount({ shift }: { shift: ShiftPublic }) {
  return (
    <section className="rounded-xl border bg-card p-4">
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
            <dt className="font-medium">Selisih</dt>
            <dd className="text-right font-semibold">
              <CashVariance shift={shift} />
            </dd>
          </>
        )}
      </dl>
      {shift.cash_variance != null && shift.cash_variance < 0 && (
        <p className="mt-3 border-t pt-3 text-sm">
          Keputusan: <ShiftDecision shift={shift} />
        </p>
      )}
    </section>
  )
}

function Takings({ shift }: { shift: ShiftPublic }) {
  return (
    <section className="rounded-xl border bg-card p-4">
      <h2 className="font-medium">Pembayaran</h2>
      <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 tabular-nums">
        {shift.payment_totals.map((total) => (
          <div key={total.method_name} className="contents">
            <dt className="text-muted-foreground">{total.method_name}</dt>
            <dd className="text-right">{rupiah(total.amount)}</dd>
          </div>
        ))}
        <dt className="font-medium">Penjualan bersih</dt>
        <dd className="text-right font-semibold">{rupiah(shift.net_sales)}</dd>
      </dl>
      <p className="mt-3 border-t pt-3 text-sm text-muted-foreground">
        {shift.sale_count} penjualan · {shift.return_count} retur atau tukar
        tambah · {shift.void_count} dibatalkan
      </p>
    </section>
  )
}

/** The Owner decides who bears a short drawer (rule 3). */
function ResolveShortage({ shift }: { shift: ShiftPublic }) {
  const staff = useQuery(opnamesListStaffOptions())
  const [resolution, setResolution] = useState<Resolution>('company_loss')
  const [chargedId, setChargedId] = useState(String(shift.cashier_id))
  const resolve = useMutation({
    ...shiftsResolveShiftMutation(),
    onSuccess: (resolved) => {
      queryClient.setQueryData(
        shiftsReadShiftQueryKey({ path: { shift_id: resolved.id } }),
        resolved,
      )
      queryClient.invalidateQueries({ queryKey: shiftsListShiftsQueryKey() })
      toast.success(`Selisih kas shift ${resolved.number} diputuskan.`)
    },
  })
  const shortage = -(shift.cash_variance ?? 0)
  return (
    <section className="mt-4 max-w-xl rounded-xl border border-destructive/40 bg-card p-4">
      <h2 className="font-medium">
        Kas kurang {rupiah(shortage)}: siapa yang menanggung?
      </h2>
      <fieldset className="mt-3 grid gap-2">
        <legend className="sr-only">Keputusan</legend>
        {(Object.keys(RESOLUTION_LABELS) as Resolution[]).map((value) => (
          <label key={value} className="flex items-center gap-2.5">
            <input
              type="radio"
              name="resolution"
              value={value}
              checked={resolution === value}
              onChange={() => setResolution(value)}
              className="size-4 accent-primary"
            />
            {RESOLUTION_LABELS[value]}
          </label>
        ))}
      </fieldset>
      {resolution === 'employee_charge' && (
        <Field id="charged-user" label="Karyawan" className="mt-3">
          <Select value={chargedId} onValueChange={setChargedId}>
            <SelectTrigger id="charged-user" className="w-full sm:w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {staff.data?.map((person) => (
                <SelectItem key={person.id} value={String(person.id)}>
                  {person.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
      {resolve.isError && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {errorMessage(resolve.error)}
        </p>
      )}
      <Button
        className="mt-4"
        disabled={resolve.isPending}
        onClick={() =>
          resolve.mutate({
            path: { shift_id: shift.id },
            body: {
              resolution,
              charged_user_id:
                resolution === 'employee_charge' ? Number(chargedId) : null,
            },
          })
        }
      >
        {resolve.isPending ? 'Menyimpan…' : 'Simpan keputusan'}
      </Button>
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
      {shift.payment_totals.map((total) => (
        <SlipRow
          key={total.method_name}
          label={total.method_name}
          value={rupiah(total.amount)}
        />
      ))}
      <SlipRow label="Penjualan bersih" value={rupiah(shift.net_sales)} />
      <p>
        {shift.sale_count} jual, {shift.return_count} retur/tukar,{' '}
        {shift.void_count} batal
      </p>
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
