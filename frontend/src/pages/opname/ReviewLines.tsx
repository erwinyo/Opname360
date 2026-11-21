import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import type {
  LineResolutionSave,
  LineShow,
  OpnameLinePublic,
  OpnamePublic,
  Resolution,
  ShortageReason,
} from '@/client'
import {
  opnamesListLinesOptions,
  opnamesListStaffOptions,
  opnamesRecountLineMutation,
  opnamesSaveResolutionMutation,
} from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import {
  groupDigits,
  money,
  onlyDigits,
  parseQuantity,
  quantity,
  rupiah,
  skuName,
} from '@/lib/format'
import { RESOLUTION_LABELS, SHORTAGE_REASON_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { refreshOpname } from '@/pages/opname/refresh'
import { LineBatch } from '@/pages/opname/shared'

const PAGE_SIZE = 50

const SHOW_LABELS: [LineShow, string][] = [
  ['variance', 'Ada selisih'],
  ['needs_cost', 'Perlu harga'],
  ['all', 'Semua'],
]

/** The approver's view: System and Physical Quantity, Variance and value. */
export function ReviewLines({ opname }: { opname: OpnamePublic }) {
  const [show, setShow] = useState<LineShow>('variance')
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(typed.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [typed])
  const lines = useQuery({
    ...opnamesListLinesOptions({
      path: { opname_id: opname.id },
      query: { show, search: search || undefined, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const estimated = opname.status === 'review'

  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold">
        {opname.is_opening
          ? 'Stok awal'
          : estimated
            ? 'Tinjau selisih'
            : 'Selisih'}
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:max-w-md">
        {opname.is_opening ? (
          <Total
            label="Stok awal"
            count={opname.surplus_count ?? 0}
            value={opname.surplus_value ?? '0'}
            estimated={estimated}
          />
        ) : (
          <>
            <Total
              label="Kurang"
              count={opname.shortage_count ?? 0}
              value={opname.shortage_value ?? '0'}
              estimated={estimated}
              className="text-destructive"
            />
            <Total
              label="Lebih"
              count={opname.surplus_count ?? 0}
              value={opname.surplus_value ?? '0'}
              estimated={estimated}
            />
          </>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border bg-card p-0.5">
          {SHOW_LABELS.map(([value, label]) => [
            value,
            opname.is_opening && value === 'variance' ? 'Ada stok' : label,
          ]).map(([value, label]) => (
            <Button
              key={value}
              size="sm"
              variant={show === value ? 'secondary' : 'ghost'}
              aria-pressed={show === value}
              onClick={() => {
                setShow(value as LineShow)
                setOffset(0)
              }}
            >
              {label}
            </Button>
          ))}
        </div>
        <div className="relative min-w-56 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Cari nama, kode, atau barcode"
            aria-label="Cari SKU dalam opname"
            className="bg-card pl-8"
          />
        </div>
      </div>

      {lines.isError && (
        <p className="mt-4 text-destructive">{errorMessage(lines.error)}</p>
      )}
      {lines.data?.total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {show === 'variance'
            ? 'Tidak ada selisih: semua hitungan sama dengan stok sistem.'
            : show === 'needs_cost'
              ? 'Semua selisih lebih sudah punya harga.'
              : 'Tidak ada SKU di sini.'}
        </p>
      )}
      <ul className="mt-3 grid gap-3">
        {lines.data?.items.map((line) => (
          <ReviewLine key={line.id} opname={opname} line={line} />
        ))}
      </ul>
      {lines.data && (
        <Pager
          offset={offset}
          pageSize={PAGE_SIZE}
          total={lines.data.total}
          unit="SKU"
          onChange={setOffset}
        />
      )}
    </section>
  )
}

function Total({
  label,
  count,
  value,
  estimated,
  className,
}: {
  label: string
  count: number
  value: string
  estimated: boolean
  className?: string
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        {label} · {count} SKU
      </p>
      <p className={cn('text-xl font-semibold tabular-nums', className)}>
        {money(value)}
      </p>
      {estimated && <p className="text-xs text-muted-foreground">perkiraan</p>}
    </div>
  )
}

function signed(value: string): string {
  const number = Number(value)
  return `${number > 0 ? '+' : ''}${quantity(number)}`
}

function ReviewLine({
  opname,
  line,
}: {
  opname: OpnamePublic
  line: OpnameLinePublic
}) {
  const reviewing = opname.status === 'review' && opname.can_approve
  const variance = Number(line.variance ?? 0)
  const recount = useMutation({
    ...opnamesRecountLineMutation(),
    onSuccess: () => {
      void refreshOpname(opname.id)
      toast.success(`${skuName(line)} dihitung ulang.`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <li className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{skuName(line)}</p>
          <p className="text-sm text-muted-foreground tabular-nums">
            {line.code} · {line.barcode}
          </p>
          <LineBatch line={line} />
        </div>
        {line.moved_while_counting && (
          <Badge
            variant="outline"
            className="border-amber-500/50 text-amber-700 dark:text-amber-400"
            title="Terjual, diretur, atau diterima di antara hitungan pertama dan terakhir. Sebaiknya hitung ulang."
          >
            Bergerak saat dihitung
          </Badge>
        )}
        {line.recount && (
          <Badge variant="outline">
            {line.counted ? 'Sudah dihitung ulang' : 'Menunggu hitung ulang'}
          </Badge>
        )}
      </div>

      {line.counted && (
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">Sistem</dt>
            <dd className="font-medium tabular-nums">
              {quantity(line.system_quantity ?? 0)} {line.stock_unit}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Fisik</dt>
            <dd className="font-medium tabular-nums">
              {quantity(line.physical_quantity ?? 0)} {line.stock_unit}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Selisih</dt>
            <dd
              className={cn(
                'font-semibold tabular-nums',
                variance < 0 && 'text-destructive',
                variance > 0 && 'text-primary',
              )}
            >
              {signed(line.variance ?? '0')} {line.stock_unit}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Nilai</dt>
            <dd className="font-medium tabular-nums">
              {line.variance_value == null
                ? 'Harga belum ada'
                : money(line.variance_value)}
            </dd>
          </div>
        </dl>
      )}

      {line.counted && variance !== 0 && (
        <Decision opname={opname} line={line} editable={reviewing} />
      )}

      {reviewing && line.counted && (
        <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
          <Button
            variant="outline"
            size="sm"
            disabled={recount.isPending}
            onClick={() =>
              recount.mutate({
                path: { opname_id: opname.id, line_id: line.id },
              })
            }
          >
            Hitung ulang
          </Button>
        </div>
      )}
    </li>
  )
}

const NO_EMPLOYEE = 'none'

/**
 * Why a Shortage happened and who bears it, or the unit cost a Surplus or
 * opening stock needs. Saved as soon as something is chosen.
 */
function Decision({
  opname,
  line,
  editable,
}: {
  opname: OpnamePublic
  line: OpnameLinePublic
  editable: boolean
}) {
  const me = useMe()
  const isOwner = me.data?.role === 'owner'
  const shortage = Number(line.variance) < 0 && !opname.is_opening
  const needsCostInput =
    opname.is_opening || line.needs_cost || line.entered_unit_cost != null
  const staff = useQuery({
    ...opnamesListStaffOptions(),
    enabled: editable && shortage && isOwner,
  })
  const [amount, setAmount] = useState(
    line.charge_amount == null ? '' : String(line.charge_amount),
  )
  const [cost, setCost] = useState(
    line.entered_unit_cost == null
      ? ''
      : String(Math.round(Number(line.entered_unit_cost))),
  )
  const save = useMutation({
    ...opnamesSaveResolutionMutation(),
    onSuccess: () => void refreshOpname(opname.id),
    onError: (error) => toast.error(errorMessage(error)),
  })
  const current: LineResolutionSave = {
    shortage_reason: line.shortage_reason,
    resolution: line.resolution,
    charged_user_id: line.charged_user_id,
    charge_amount: line.charge_amount,
    unit_cost: line.entered_unit_cost,
  }
  const send = (change: Partial<LineResolutionSave>) =>
    save.mutate({
      path: { opname_id: opname.id, line_id: line.id },
      body: { ...current, ...change },
    })
  const resolution: Resolution = line.resolution ?? 'company_loss'
  const charged = resolution === 'employee_charge'
  const estimate = Math.round(-Number(line.variance_value ?? 0))

  if (!editable) {
    if (!shortage) return null
    return (
      <p className="mt-3 border-t pt-3 text-sm">
        {line.shortage_reason
          ? SHORTAGE_REASON_LABELS[line.shortage_reason]
          : 'Alasan belum dipilih'}{' '}
        · {RESOLUTION_LABELS[resolution]}
        {charged && line.charged_user_name && (
          <>
            {' '}
            oleh {line.charged_user_name} (
            {rupiah(line.charge_amount ?? estimate)})
          </>
        )}
      </p>
    )
  }

  return (
    <div className="mt-3 grid gap-3 border-t pt-3 sm:grid-cols-2">
      {shortage && (
        <>
          <div className="grid gap-2">
            <Label htmlFor={`reason-${line.id}`}>Alasan kurang</Label>
            <Select
              value={line.shortage_reason ?? undefined}
              onValueChange={(value) =>
                send({ shortage_reason: value as ShortageReason })
              }
            >
              <SelectTrigger
                id={`reason-${line.id}`}
                className={cn(
                  'w-full',
                  !line.shortage_reason && 'border-amber-500/60',
                )}
              >
                <SelectValue placeholder="Pilih alasan" />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(SHORTAGE_REASON_LABELS) as ShortageReason[]).map(
                  (value) => (
                    <SelectItem key={value} value={value}>
                      {SHORTAGE_REASON_LABELS[value]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`resolution-${line.id}`}>Ditanggung</Label>
            <Select
              value={resolution}
              disabled={!isOwner}
              onValueChange={(value) =>
                send({
                  resolution: value as Resolution,
                  charged_user_id: null,
                  charge_amount: null,
                })
              }
            >
              <SelectTrigger id={`resolution-${line.id}`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(RESOLUTION_LABELS) as Resolution[]).map(
                  (value) => (
                    <SelectItem key={value} value={value}>
                      {RESOLUTION_LABELS[value]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
            {!isOwner && (
              <p className="text-sm text-muted-foreground">
                Hanya Pemilik yang bisa membebankan ke karyawan.
              </p>
            )}
          </div>
          {charged && isOwner && (
            <>
              <div className="grid gap-2">
                <Label htmlFor={`employee-${line.id}`}>Karyawan</Label>
                <Select
                  value={
                    line.charged_user_id == null
                      ? NO_EMPLOYEE
                      : String(line.charged_user_id)
                  }
                  onValueChange={(value) =>
                    send({
                      charged_user_id:
                        value === NO_EMPLOYEE ? null : Number(value),
                    })
                  }
                >
                  <SelectTrigger
                    id={`employee-${line.id}`}
                    className={cn(
                      'w-full',
                      line.charged_user_id == null && 'border-amber-500/60',
                    )}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_EMPLOYEE}>Pilih karyawan</SelectItem>
                    {staff.data?.map((user) => (
                      <SelectItem key={user.id} value={String(user.id)}>
                        {user.full_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor={`amount-${line.id}`}>Jumlah ganti rugi</Label>
                <Input
                  id={`amount-${line.id}`}
                  inputMode="numeric"
                  value={groupDigits(amount)}
                  placeholder={groupDigits(String(estimate))}
                  onChange={(event) =>
                    setAmount(onlyDigits(event.target.value))
                  }
                  onBlur={() =>
                    send({
                      charge_amount: amount === '' ? null : Number(amount),
                    })
                  }
                  className="tabular-nums"
                />
                <p className="text-sm text-muted-foreground">
                  Kosongkan untuk memakai nilai selisih.
                </p>
              </div>
            </>
          )}
        </>
      )}
      {needsCostInput && Number(line.variance) > 0 && (
        <div className="grid gap-2">
          <Label htmlFor={`cost-${line.id}`}>Harga per {line.stock_unit}</Label>
          <Input
            id={`cost-${line.id}`}
            inputMode="numeric"
            value={groupDigits(cost)}
            onChange={(event) => setCost(onlyDigits(event.target.value))}
            onBlur={() => {
              const typed = parseQuantity(cost)
              send({ unit_cost: Number.isFinite(typed) ? cost : null })
            }}
            className={cn(
              'tabular-nums',
              line.needs_cost && 'border-amber-500/60',
            )}
          />
          <p className="text-sm text-muted-foreground">
            {opname.is_opening
              ? 'Harga pokok stok awal, dari harga beli terakhir di impor.'
              : 'SKU ini belum pernah punya harga beli.'}
          </p>
        </div>
      )}
    </div>
  )
}
