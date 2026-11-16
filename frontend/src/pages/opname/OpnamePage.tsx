import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { toast } from 'sonner'

import { opnamesListLines } from '@/client'
import type { LineShow, OpnamePublic } from '@/client'
import {
  opnamesCancelOpnameMutation,
  opnamesCloseCountingMutation,
  opnamesConfirmZeroMutation,
  opnamesListLinesOptions,
  opnamesReadOpnameOptions,
} from '@/client/@tanstack/react-query.gen'
import { BackLink, Facts } from '@/components/documents'
import { FormDialog } from '@/components/FormDialog'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDateTime, skuName } from '@/lib/format'
import { cn } from '@/lib/utils'
import { refreshOpname } from '@/pages/opname/refresh'
import { ReviewLines } from '@/pages/opname/ReviewLines'
import { OpnameStatusBadge, Progress } from '@/pages/opname/shared'

const PAGE_SIZE = 50

export function OpnamePage() {
  const opnameId = Number(useParams().opnameId)
  const opname = useQuery(
    opnamesReadOpnameOptions({ path: { opname_id: opnameId } }),
  )
  const [cancelling, setCancelling] = useState(false)
  const [zeroing, setZeroing] = useState<number[] | null>(null)
  const close = useMutation({
    ...opnamesCloseCountingMutation(),
    onSuccess: (closed) => {
      void refreshOpname(closed.id)
      toast.success(`Penghitungan ${closed.number} ditutup.`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const findUncounted = useMutation({
    mutationFn: async () => {
      const { data } = await opnamesListLines({
        path: { opname_id: opnameId },
        query: { show: 'uncounted', limit: 2000 },
        throwOnError: true,
      })
      return data.items.map((line) => line.id)
    },
    onSuccess: setZeroing,
    onError: (error) => toast.error(errorMessage(error)),
  })

  if (opname.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (opname.isError) {
    return (
      <>
        <BackLink to="/stok-opname" label="Stok Opname" />
        <p className="mt-4 text-destructive">{errorMessage(opname.error)}</p>
      </>
    )
  }
  const data = opname.data
  const unfinished = data.status === 'counting' || data.status === 'review'
  const uncounted = data.line_count - data.counted_count

  return (
    <>
      <BackLink to="/stok-opname" label="Stok Opname" />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight tabular-nums">
          {data.number}
        </h1>
        <OpnameStatusBadge status={data.status} />
        {data.is_opening && <Badge variant="outline">Opname awal</Badge>}
        {unfinished && (
          <Button
            variant="outline"
            className="ml-auto"
            onClick={() => setCancelling(true)}
          >
            Batalkan opname
          </Button>
        )}
      </div>
      <p className="mt-1 text-muted-foreground">{data.scope_label}</p>

      <Facts facts={facts(data)} note={data.note} />

      <section className="mt-4 rounded-xl border bg-card p-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-medium">Progres</h2>
          <span className="text-sm text-muted-foreground tabular-nums">
            {data.counted_count} dari {data.line_count} SKU dihitung
          </span>
        </div>
        <div className="mt-3">
          <Progress done={data.counted_count} total={data.line_count} />
        </div>
        {data.status === 'counting' && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              disabled={close.isPending || uncounted > 0}
              onClick={() => close.mutate({ path: { opname_id: data.id } })}
            >
              Tutup penghitungan
            </Button>
            {uncounted > 0 && (
              <Button
                variant="outline"
                disabled={findUncounted.isPending}
                onClick={() => findUncounted.mutate()}
              >
                Konfirmasi nol semua yang belum dihitung
              </Button>
            )}
          </div>
        )}
        {data.status === 'counting' && uncounted > 0 && (
          <p className="mt-2 text-sm text-muted-foreground">
            Penghitungan bisa ditutup setelah semua SKU dihitung atau
            dikonfirmasi nol.
          </p>
        )}
      </section>

      {data.unknown_barcodes.length > 0 && <UnknownBarcodes data={data} />}

      {data.status === 'review' && !data.can_approve && (
        <p className="mt-4 rounded-xl border border-dashed p-4 text-muted-foreground">
          Anda checker di opname ini, jadi selisihnya tidak ditampilkan dan
          peninjauan dilakukan Pemilik atau Admin lain.
        </p>
      )}

      {data.revealed ? (
        <ReviewLines opname={data} />
      ) : (
        <ProgressLines opname={data} onConfirmZero={setZeroing} />
      )}

      {cancelling && (
        <CancelDialog opname={data} onClose={() => setCancelling(false)} />
      )}
      {zeroing && (
        <ZeroDialog
          opname={data}
          lineIds={zeroing}
          onClose={() => setZeroing(null)}
        />
      )}
    </>
  )
}

function facts(data: OpnamePublic): [string, string][] {
  const rows: [string, string][] = [
    ['Lokasi', data.location_name],
    [
      'Dibuka',
      `${data.opened_by_name ?? 'Sistem'} · ${formatDateTime(data.opened_at)}`,
    ],
    [
      'Checker',
      data.checkers.map((checker) => checker.full_name).join(', '),
    ],
  ]
  if (data.counting_closed_at) {
    rows.push([
      'Penghitungan ditutup',
      `${data.counting_closed_by_name ?? ''} · ${formatDateTime(data.counting_closed_at)}`,
    ])
  }
  if (data.approved_at) {
    rows.push([
      'Disetujui',
      `${data.approved_by_name ?? ''} · ${formatDateTime(data.approved_at)}`,
    ])
  }
  if (data.cancelled_at) {
    rows.push([
      'Dibatalkan',
      `${data.cancelled_by_name ?? ''} · ${formatDateTime(data.cancelled_at)}`,
    ])
  }
  return rows
}

function UnknownBarcodes({ data }: { data: OpnamePublic }) {
  return (
    <section className="mt-4 rounded-xl border border-amber-500/40 bg-card p-4">
      <h2 className="font-medium">Barcode tidak dikenal</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Di-scan checker tetapi tidak ada di katalog. Periksa barangnya, lalu
        tambahkan produknya atau perbaiki barcode-nya.
      </p>
      <ul className="mt-3 divide-y">
        {data.unknown_barcodes.map((unknown) => (
          <li
            key={unknown.code}
            className="flex flex-wrap items-baseline gap-x-3 py-2"
          >
            <span className="font-medium tabular-nums">{unknown.code}</span>
            <span className="text-sm text-muted-foreground">
              {unknown.times}× · terakhir {unknown.last_scanned_by_name},{' '}
              {formatDateTime(unknown.last_scanned_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

const SHOW_LABELS: [LineShow, string][] = [
  ['all', 'Semua'],
  ['uncounted', 'Belum dihitung'],
  ['counted', 'Sudah dihitung'],
]

function ProgressLines({
  opname,
  onConfirmZero,
}: {
  opname: OpnamePublic
  onConfirmZero: (lineIds: number[]) => void
}) {
  const [show, setShow] = useState<LineShow>('all')
  const [selected, setSelected] = useState<number[]>([])
  const canZero = opname.status === 'counting'
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
  // Only lines still uncounted on this page can be confirmed zero.
  const uncountedHere = new Set(
    lines.data?.items.filter((line) => !line.counted).map((line) => line.id),
  )
  const chosen = selected.filter((id) => uncountedHere.has(id))

  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold">SKU dalam opname</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2">
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
          Tidak ada SKU di sini.
        </p>
      )}
      {canZero && chosen.length > 0 && (
        <div className="mt-3 flex items-center gap-3">
          <Button variant="outline" onClick={() => onConfirmZero(chosen)}>
            Konfirmasi nol ({chosen.length})
          </Button>
          <Button variant="ghost" onClick={() => setSelected([])}>
            Batal pilih
          </Button>
        </div>
      )}
      {lines.data && lines.data.total > 0 && (
        <>
          <div className="mt-3 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  {canZero && (
                    <TableHead className="w-10">
                      <span className="sr-only">Pilih</span>
                    </TableHead>
                  )}
                  <TableHead>Barang</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.data.items.map((line) => (
                  <TableRow key={line.id}>
                    {canZero && (
                      <TableCell>
                        {!line.counted && (
                          <input
                            type="checkbox"
                            className="size-4 accent-primary"
                            aria-label={`Pilih ${skuName(line)}`}
                            checked={selected.includes(line.id)}
                            onChange={() =>
                              setSelected((ids) =>
                                ids.includes(line.id)
                                  ? ids.filter((id) => id !== line.id)
                                  : [...ids, line.id],
                              )
                            }
                          />
                        )}
                      </TableCell>
                    )}
                    <TableCell>
                      <span className="font-medium">{skuName(line)}</span>
                      <span className="block text-sm text-muted-foreground tabular-nums">
                        {line.code} · {line.barcode}
                      </span>
                    </TableCell>
                    <TableCell
                      className={cn(
                        'whitespace-nowrap',
                        !line.counted && 'text-muted-foreground',
                      )}
                    >
                      {line.counted ? 'Sudah dihitung' : 'Belum dihitung'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={lines.data.total}
            unit="SKU"
            onChange={setOffset}
          />
        </>
      )}
    </section>
  )
}

function CancelDialog({
  opname,
  onClose,
}: {
  opname: OpnamePublic
  onClose: () => void
}) {
  const cancel = useMutation({
    ...opnamesCancelOpnameMutation(),
    onSuccess: () => {
      void refreshOpname(opname.id)
      toast.success(`Stok opname ${opname.number} dibatalkan.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Batalkan ${opname.number}?`}
      description="Hitungannya disimpan tetapi tidak dipakai, dan stok tidak berubah. SKU-nya bisa dihitung di opname baru."
      submitLabel="Batalkan opname"
      destructive
      pending={cancel.isPending}
      error={cancel.error}
      onSubmit={() => cancel.mutate({ path: { opname_id: opname.id } })}
      onClose={onClose}
    />
  )
}

function ZeroDialog({
  opname,
  lineIds,
  onClose,
}: {
  opname: OpnamePublic
  lineIds: number[]
  onClose: () => void
}) {
  const confirm = useMutation({
    ...opnamesConfirmZeroMutation(),
    onSuccess: () => {
      void refreshOpname(opname.id)
      toast.success(`${lineIds.length} SKU dikonfirmasi nol.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Konfirmasi nol untuk ${lineIds.length} SKU?`}
      description="Artinya barangnya dicari dan memang tidak ada. Stok sistemnya dicatat sekarang; kalau ternyata ada barangnya, selisihnya kelihatan saat peninjauan."
      submitLabel="Konfirmasi nol"
      pending={confirm.isPending}
      error={confirm.error}
      onSubmit={() =>
        confirm.mutate({
          path: { opname_id: opname.id },
          body: { line_ids: lineIds },
        })
      }
      onClose={onClose}
    />
  )
}
