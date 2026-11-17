import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ClipboardCheckIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { reportsFastMovingOptions } from '@/client/@tanstack/react-query.gen'
import {
  CategoryFilter,
  DateInput,
  Empty,
  Filters,
  ReportHeader,
} from '@/components/reports'
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
import { formatDate, quantity, rupiah, skuName, today } from '@/lib/format'
import { ALL, chosen, daysAgo, withQuery } from '@/lib/reports'
import { cn } from '@/lib/utils'
import type { OpnameFromReport } from '@/pages/opname/OpenOpnamePage'

export function FastMovingPage() {
  const navigate = useNavigate()
  const [start, setStart] = useState(() => daysAgo(29))
  const [end, setEnd] = useState(today)
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const query = {
    start,
    end,
    category_id: chosen(categoryId),
    sub_category_id: chosen(subCategoryId),
  }
  const report = useQuery({
    ...reportsFastMovingOptions({ query }),
    placeholderData: keepPreviousData,
  })
  const rows = report.data?.rows ?? []

  const opname = () => {
    const state: OpnameFromReport = {
      skus: rows.map((row) => ({ ...row, id: row.sku_id })),
      note: `Fast Moving ${formatDate(start)} s.d. ${formatDate(end)}`,
    }
    navigate('/stok-opname/baru', { state })
  }

  return (
    <>
      <ReportHeader
        title="Fast Moving"
        description="SKU yang paling banyak terjual, dikurangi yang diretur. Bawaannya 30 hari terakhir."
        excel={withQuery('reports/fast-moving/excel', query)}
      />
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
        <CategoryFilter
          categoryId={categoryId}
          subCategoryId={subCategoryId}
          onChange={(category, sub) => {
            setCategoryId(category)
            setSubCategoryId(sub)
          }}
        />
      </Filters>
      {report.isError && (
        <p className="mt-6 text-destructive">{errorMessage(report.error)}</p>
      )}
      {report.data && rows.length === 0 && (
        <Empty>Belum ada yang terjual dalam periode ini.</Empty>
      )}
      {rows.length > 0 && (
        <>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {rows.length} SKU teratas
            </p>
            <Button variant="outline" onClick={opname}>
              <ClipboardCheckIcon />
              Opname {rows.length} SKU ini
            </Button>
          </div>
          <div className="mt-2 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10 text-right">#</TableHead>
                  <TableHead>Barang</TableHead>
                  <TableHead className="text-right">Terjual</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">
                    Penjualan bersih
                  </TableHead>
                  <TableHead className="text-right">Stok</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={row.sku_id}>
                    <TableCell className="text-right text-muted-foreground tabular-nums">
                      {index + 1}
                    </TableCell>
                    <TableCell>
                      <Link to={`/stok/${row.sku_id}`} className="font-medium">
                        {skuName(row)}
                      </Link>
                      <span className="block text-xs text-muted-foreground">
                        {row.code} · {row.category_name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {quantity(row.units_sold)} {row.stock_unit}
                      <span className="block text-xs text-muted-foreground sm:hidden">
                        {rupiah(row.net_sales)}
                      </span>
                    </TableCell>
                    <TableCell className="hidden text-right whitespace-nowrap tabular-nums sm:table-cell">
                      {rupiah(row.net_sales)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-right whitespace-nowrap tabular-nums',
                        Number(row.stock) < 0 &&
                          'font-semibold text-destructive',
                      )}
                    >
                      {quantity(row.stock)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </>
  )
}
