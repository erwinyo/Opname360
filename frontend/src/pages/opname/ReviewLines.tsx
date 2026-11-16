import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import type { LineShow, OpnameLinePublic, OpnamePublic } from '@/client'
import {
  opnamesListLinesOptions,
  opnamesRecountLineMutation,
} from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { money, quantity, skuName } from '@/lib/format'
import { cn } from '@/lib/utils'
import { refreshOpname } from '@/pages/opname/refresh'

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
        {estimated ? 'Tinjau selisih' : 'Selisih'}
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:max-w-md">
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
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border bg-card p-0.5">
          {SHOW_LABELS.map(([value, label]) => (
            <Button
              key={value}
              size="sm"
              variant={show === value ? 'secondary' : 'ghost'}
              aria-pressed={show === value}
              onClick={() => {
                setShow(value)
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
      {estimated && (
        <p className="text-xs text-muted-foreground">perkiraan</p>
      )}
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
