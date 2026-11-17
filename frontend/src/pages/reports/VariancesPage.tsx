import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import type { VarianceFigures, VarianceGroupBy } from '@/client'
import { reportsVariancesOptions } from '@/client/@tanstack/react-query.gen'
import {
  CategoryFilter,
  DateInput,
  Empty,
  Filters,
  ReportHeader,
} from '@/components/reports'
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
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { money, quantity, today } from '@/lib/format'
import { ALL, chosen, withQuery } from '@/lib/reports'
import { cn } from '@/lib/utils'

const GROUPS: Record<VarianceGroupBy, { label: string; title: string }> = {
  sku: { label: 'Per SKU', title: 'Barang' },
  reason: { label: 'Per alasan', title: 'Alasan' },
  resolution: { label: 'Per keputusan', title: 'Keputusan' },
}

export function VariancesPage() {
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const [groupBy, setGroupBy] = useState<VarianceGroupBy>('sku')
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const query = {
    start,
    end,
    group_by: groupBy,
    category_id: chosen(categoryId),
    sub_category_id: chosen(subCategoryId),
  }
  const report = useQuery({
    ...reportsVariancesOptions({ query }),
    placeholderData: keepPreviousData,
  })
  const data = report.data

  return (
    <>
      <ReportHeader
        title="Selisih Opname"
        description="Selisih kurang dan lebih dari stok opname yang disetujui dalam periode ini, dalam jumlah dan nilai."
        excel={withQuery('reports/variances/excel', query)}
      />
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
        <Select
          value={groupBy}
          onValueChange={(value) => setGroupBy(value as VarianceGroupBy)}
        >
          <SelectTrigger className="bg-card" aria-label="Kelompokkan">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(GROUPS) as VarianceGroupBy[]).map((key) => (
              <SelectItem key={key} value={key}>
                {GROUPS[key].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
      {data && data.rows.length === 0 && (
        <Empty>
          Tidak ada selisih dari opname yang disetujui dalam periode ini.
        </Empty>
      )}
      {data && data.rows.length > 0 && (
        <div className="mt-4 rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{GROUPS[data.group_by].title}</TableHead>
                <TableHead className="text-right">Kurang</TableHead>
                <TableHead className="text-right">Lebih</TableHead>
                <TableHead className="hidden text-right md:table-cell">
                  Selisih bersih
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row) => (
                <TableRow key={row.key}>
                  <TableCell>
                    {data.group_by === 'sku' ? (
                      <Link to={`/stok/${row.key}`} className="font-medium">
                        {row.label}
                      </Link>
                    ) : (
                      <span className="font-medium">{row.label}</span>
                    )}
                    <span className="block text-xs text-muted-foreground">
                      {[row.code, `${row.line_count} baris`]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </TableCell>
                  <Side
                    figures={row}
                    side="shortage"
                    unit={row.stock_unit ?? null}
                  />
                  <Side
                    figures={row}
                    side="surplus"
                    unit={row.stock_unit ?? null}
                  />
                  <TableCell className="hidden text-right whitespace-nowrap tabular-nums md:table-cell">
                    {money(row.net_value)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell className="font-semibold">Total</TableCell>
                <Side figures={data.total} side="shortage" unit={null} />
                <Side figures={data.total} side="surplus" unit={null} />
                <TableCell className="hidden text-right font-semibold whitespace-nowrap tabular-nums md:table-cell">
                  {money(data.total.net_value)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>
      )}
    </>
  )
}

/** Value first, the quantity under it; a dash when there is none. */
function Side({
  figures,
  side,
  unit,
}: {
  figures: VarianceFigures
  side: 'shortage' | 'surplus'
  unit: string | null
}) {
  const amount = Number(figures[`${side}_quantity`])
  return (
    <TableCell
      className={cn(
        'text-right whitespace-nowrap tabular-nums',
        amount === 0 && 'text-muted-foreground',
      )}
    >
      {amount === 0 ? (
        '—'
      ) : (
        <>
          {money(figures[`${side}_value`])}
          <span className="block text-xs text-muted-foreground">
            {quantity(amount)}
            {unit ? ` ${unit}` : ''}
          </span>
        </>
      )}
    </TableCell>
  )
}
