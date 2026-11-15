import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { DocumentStatus } from '@/client'
import { goodsReceiptsListReceiptsOptions } from '@/client/@tanstack/react-query.gen'
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
import { formatDate, money } from '@/lib/format'
import { PAYMENT_LABELS, STATUS_LABELS } from '@/lib/labels'

const PAGE_SIZE = 50
const ALL = 'all'

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge variant={status === 'completed' ? 'secondary' : 'outline'}>
      {STATUS_LABELS[status]}
    </Badge>
  )
}

export function GoodsReceiptsPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState(ALL)
  const [offset, setOffset] = useState(0)
  const receipts = useQuery({
    ...goodsReceiptsListReceiptsOptions({
      query: {
        status: status === ALL ? undefined : (status as DocumentStatus),
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })
  const total = receipts.data?.total ?? 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Barang Masuk
          </h1>
          <p className="mt-1 text-muted-foreground">
            Barang yang diterima dari pemasok. Stok bertambah saat dokumen
            diselesaikan.
          </p>
        </div>
        <Button asChild>
          <Link to="/barang-masuk/baru">
            <PlusIcon />
            Barang masuk baru
          </Link>
        </Button>
      </div>

      <div className="mt-6">
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value)
            setOffset(0)
          }}
        >
          <SelectTrigger className="bg-card" aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Semua status</SelectItem>
            <SelectItem value="draft">{STATUS_LABELS.draft}</SelectItem>
            <SelectItem value="completed">{STATUS_LABELS.completed}</SelectItem>
            <SelectItem value="reversed">{STATUS_LABELS.reversed}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {receipts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(receipts.error)}</p>
      )}
      {receipts.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {status === ALL
            ? 'Belum ada barang masuk.'
            : 'Tidak ada barang masuk dengan status ini.'}
        </p>
      )}

      {total > 0 && (
        <>
          <div className="mt-4 overflow-x-auto rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nomor</TableHead>
                  <TableHead>Tanggal</TableHead>
                  <TableHead>Pemasok</TableHead>
                  <TableHead className="hidden text-right md:table-cell">
                    Baris
                  </TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="hidden md:table-cell">
                    Pembayaran
                  </TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receipts.data?.items.map((receipt) => (
                  <TableRow
                    key={receipt.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/barang-masuk/${receipt.id}`)}
                  >
                    <TableCell>
                      <Link
                        to={`/barang-masuk/${receipt.id}`}
                        className="font-medium tabular-nums"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {receipt.number ?? 'Draf'}
                      </Link>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(receipt.received_on)}
                    </TableCell>
                    <TableCell>{receipt.supplier_name}</TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {receipt.line_count}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(receipt.total_cost)}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {PAYMENT_LABELS[receipt.payment_status]}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={receipt.status} />
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
            unit="dokumen"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
