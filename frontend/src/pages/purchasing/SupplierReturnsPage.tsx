import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { DocumentStatus } from '@/client'
import { supplierReturnsListReturnsOptions } from '@/client/@tanstack/react-query.gen'
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

export function SupplierReturnsPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<DocumentStatus | null>(null)
  const [offset, setOffset] = useState(0)
  const returns = useQuery({
    ...supplierReturnsListReturnsOptions({
      query: { status, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const total = returns.data?.total ?? 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Retur Pembelian
          </h1>
          <p className="mt-1 text-muted-foreground">
            Barang yang dikembalikan ke pemasok, selalu dari satu barang masuk.
          </p>
        </div>
        <Button asChild>
          <Link to="/retur-pembelian/baru">
            <PlusIcon />
            Retur baru
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

      {returns.isError && (
        <p className="mt-6 text-destructive">{errorMessage(returns.error)}</p>
      )}
      {returns.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          {status ? 'Tidak ada retur dengan status ini.' : 'Belum ada retur pembelian.'}
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
                  <TableHead className="hidden md:table-cell">
                    Dari barang masuk
                  </TableHead>
                  <TableHead className="text-right">Nilai retur</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {returns.data?.items.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/retur-pembelian/${item.id}`)}
                  >
                    <TableCell>
                      <Link
                        to={`/retur-pembelian/${item.id}`}
                        className="font-medium tabular-nums"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {item.number ?? 'Draf'}
                      </Link>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(item.returned_on)}
                    </TableCell>
                    <TableCell>{item.supplier_name}</TableCell>
                    <TableCell className="hidden tabular-nums md:table-cell">
                      {item.goods_receipt_number}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(item.total_refund)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} />
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
            unit="retur"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
