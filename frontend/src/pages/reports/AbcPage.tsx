import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ClipboardCheckIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { AbcClass } from '@/client'
import { reportsAbcOptions } from '@/client/@tanstack/react-query.gen'
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
import { formatDate, percent, rupiah, skuName, today } from '@/lib/format'
import { ALL, chosen, daysAgo, withQuery } from '@/lib/reports'
import { cn } from '@/lib/utils'
import type { OpnameFromReport } from '@/pages/opname/OpenOpnamePage'

const MEANING: Record<AbcClass, string> = {
  A: '80% omzet teratas',
  B: '15% berikutnya',
  C: 'sisanya, termasuk yang tidak laku',
}

export function AbcPage() {
  const navigate = useNavigate()
  const [start, setStart] = useState(() => daysAgo(29))
  const [end, setEnd] = useState(today)
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const [shown, setShown] = useState<AbcClass>('A')
  const query = {
    start,
    end,
    category_id: chosen(categoryId),
    sub_category_id: chosen(subCategoryId),
  }
  const report = useQuery({
    ...reportsAbcOptions({ query }),
    placeholderData: keepPreviousData,
  })
  const data = report.data
  const rows = data?.rows.filter((row) => row.abc_class === shown) ?? []
  const classA = data?.rows.filter((row) => row.abc_class === 'A') ?? []

  const opname = () => {
    const state: OpnameFromReport = {
      skus: classA.map((row) => ({ ...row, id: row.sku_id })),
      note: `Kelas A Kontribusi Omzet ${formatDate(start)} s.d. ${formatDate(end)}`,
    }
    navigate('/stok-opname/baru', { state })
  }

  return (
    <>
      <ReportHeader
        title="Kontribusi Omzet"
        description="Kelas ABC tiap SKU menurut penjualan bersihnya: kelas A menyumbang 80% omzet, B 15% berikutnya, C sisanya."
        excel={withQuery('reports/abc/excel', query)}
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
      {data && data.rows.length === 0 && <Empty>Belum ada SKU.</Empty>}
      {data && data.rows.length > 0 && (
        <>
          <div
            className="mt-4 grid grid-cols-3 gap-2"
            role="tablist"
            aria-label="Kelas"
          >
            {data.classes.map((total) => (
              <button
                key={total.abc_class}
                type="button"
                role="tab"
                aria-selected={shown === total.abc_class}
                onClick={() => setShown(total.abc_class)}
                className={cn(
                  'rounded-xl border bg-card p-3 text-left hover:border-primary/40',
                  shown === total.abc_class &&
                    'border-primary ring-1 ring-primary',
                )}
              >
                <span className="block font-semibold">
                  Kelas {total.abc_class}
                </span>
                <span className="block text-sm text-muted-foreground">
                  {total.sku_count} SKU · {percent(total.share)}
                </span>
                <span className="mt-1 block text-sm font-medium tabular-nums">
                  {rupiah(total.net_sales)}
                </span>
                <span className="hidden text-xs text-muted-foreground sm:block">
                  {MEANING[total.abc_class]}
                </span>
              </button>
            ))}
          </div>
          {classA.length > 0 && (
            <Button variant="outline" className="mt-3" onClick={opname}>
              <ClipboardCheckIcon />
              Opname dari Kelas A
            </Button>
          )}
          {rows.length === 0 ? (
            <Empty>Tidak ada SKU di kelas {shown}.</Empty>
          ) : (
            <div className="mt-3 rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Barang</TableHead>
                    <TableHead className="text-right">
                      Penjualan bersih
                    </TableHead>
                    <TableHead className="hidden text-right sm:table-cell">
                      Porsi
                    </TableHead>
                    <TableHead className="text-right">Kumulatif</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.sku_id}>
                      <TableCell>
                        <Link
                          to={`/stok/${row.sku_id}`}
                          className="font-medium"
                        >
                          {skuName(row)}
                        </Link>
                        <span className="block text-xs text-muted-foreground">
                          {row.code} · {row.category_name}
                        </span>
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {rupiah(row.net_sales)}
                        <span className="block text-xs text-muted-foreground sm:hidden">
                          {percent(row.share)}
                        </span>
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums sm:table-cell">
                        {percent(row.share)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {percent(row.running_share)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </>
  )
}
