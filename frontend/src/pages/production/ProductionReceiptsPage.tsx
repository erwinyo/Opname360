import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { DocumentStatus } from '@/client'
import { productionReceiptsListReceiptsOptions } from '@/client/@tanstack/react-query.gen'
import { StatusBadge } from '@/components/documents'
import { Pager } from '@/components/Pager'
import { StatusFilter } from '@/components/StatusFilter'
import { Button } from '@/components/ui/button'
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

const PAGE_SIZE = 50

export function ProductionReceiptsPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<DocumentStatus | null>(null)
  const [offset, setOffset] = useState(0)
  const receipts = useQuery({
    ...productionReceiptsListReceiptsOptions({
      query: { status, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const total = receipts.data?.total ?? 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Hasil Produksi
          </h1>
          <p className="mt-1 text-muted-foreground">
            Barang jadi buatan sendiri atau penjahit yang masuk ke stok, dengan
            biaya pembuatannya.
          </p>
        </div>
        <Button asChild>
          <Link to="/hasil-produksi/baru">
            <PlusIcon />
            Hasil produksi baru
          </Link>
        </Button>
      </div>

      <StatusFilter
        value={status}
        onChange={(value) => {
          setStatus(value)
          setOffset(0)
        }}
      />

      {receipts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(receipts.error)}</p>
      )}
      {receipts.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {status
            ? 'Tidak ada dokumen dengan status ini.'
            : 'Belum ada hasil produksi.'}
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
                  <TableHead className="text-right">Baris</TableHead>
                  <TableHead className="text-right">Biaya</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receipts.data?.items.map((receipt) => (
                  <TableRow
                    key={receipt.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/hasil-produksi/${receipt.id}`)}
                  >
                    <TableCell>
                      <Link
                        to={`/hasil-produksi/${receipt.id}`}
                        className="font-medium tabular-nums"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {receipt.number ?? 'Draf'}
                      </Link>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(receipt.produced_on)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {receipt.line_count}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(receipt.total_cost)}
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
