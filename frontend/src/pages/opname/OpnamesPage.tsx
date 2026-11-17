import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { OpnameStatus } from '@/client'
import { opnamesListOpnamesOptions } from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
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
import { formatDateTime } from '@/lib/format'
import { OPNAME_STATUS_LABELS } from '@/lib/labels'
import { OpnameStatusBadge, Progress } from '@/pages/opname/shared'

const PAGE_SIZE = 50
const ALL = 'all'

export function OpnamesPage() {
  const navigate = useNavigate()
  // The dashboard links here with ?status=review.
  const [status, setStatus] = useState<OpnameStatus | null>(
    () =>
      new URLSearchParams(window.location.search).get(
        'status',
      ) as OpnameStatus | null,
  )
  const [offset, setOffset] = useState(0)
  const opnames = useQuery({
    ...opnamesListOpnamesOptions({
      query: { status, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const total = opnames.data?.total ?? 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Stok Opname</h1>
          <p className="mt-1 text-muted-foreground">
            Hitung stok tanpa menutup toko. Stok baru berubah setelah opname
            disetujui.
          </p>
        </div>
        <Button asChild>
          <Link to="/stok-opname/baru">
            <PlusIcon />
            Buka opname
          </Link>
        </Button>
      </div>

      <div className="mt-6">
        <Select
          value={status ?? ALL}
          onValueChange={(value) => {
            setStatus(value === ALL ? null : (value as OpnameStatus))
            setOffset(0)
          }}
        >
          <SelectTrigger className="bg-card" aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Semua status</SelectItem>
            {(Object.keys(OPNAME_STATUS_LABELS) as OpnameStatus[]).map(
              (value) => (
                <SelectItem key={value} value={value}>
                  {OPNAME_STATUS_LABELS[value]}
                </SelectItem>
              ),
            )}
          </SelectContent>
        </Select>
      </div>

      {opnames.isError && (
        <p className="mt-6 text-destructive">{errorMessage(opnames.error)}</p>
      )}
      {opnames.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {status === null
            ? 'Belum ada stok opname. Mulai dengan opname parsial barang yang paling laku, atau opname awal sebelum toko memakai sistem ini.'
            : 'Tidak ada stok opname dengan status ini.'}
        </p>
      )}

      {total > 0 && (
        <>
          <div className="mt-4 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nomor</TableHead>
                  <TableHead className="hidden md:table-cell">Dibuka</TableHead>
                  <TableHead>Cakupan</TableHead>
                  <TableHead className="w-40">Dihitung</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {opnames.data?.items.map((opname) => (
                  <TableRow
                    key={opname.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/stok-opname/${opname.id}`)}
                  >
                    <TableCell>
                      <Link
                        to={`/stok-opname/${opname.id}`}
                        className="font-medium tabular-nums"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {opname.number}
                      </Link>
                    </TableCell>
                    <TableCell className="hidden whitespace-nowrap md:table-cell">
                      {formatDateTime(opname.opened_at)}
                    </TableCell>
                    <TableCell>
                      {opname.scope_label}
                      {opname.is_opening && (
                        <Badge variant="outline" className="ml-2">
                          Opname awal
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="mb-1 block text-sm text-muted-foreground tabular-nums">
                        {opname.counted_count} / {opname.line_count} SKU
                      </span>
                      <Progress
                        done={opname.counted_count}
                        total={opname.line_count}
                      />
                    </TableCell>
                    <TableCell>
                      <OpnameStatusBadge status={opname.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={total}
            unit="opname"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
