import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import type { SalesGroupBy, SalesRow } from '@/client'
import { reportsSalesOptions } from '@/client/@tanstack/react-query.gen'
import { DateInput, Filters, ReportHeader } from '@/components/reports'
import { SalesTable } from '@/components/SalesTable'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage } from '@/lib/api'
import { formatDate, today } from '@/lib/format'
import { withQuery } from '@/lib/reports'

const GROUPS: Record<SalesGroupBy, { label: string; title: string }> = {
  day: { label: 'Per hari', title: 'Tanggal' },
  cashier: { label: 'Per kasir', title: 'Kasir' },
  payment_method: { label: 'Per metode pembayaran', title: 'Metode' },
  category: { label: 'Per kategori', title: 'Kategori' },
}

/** Which Receipts make up a row: the filter for its drill-down. */
function receiptsOf(
  row: SalesRow,
  groupBy: SalesGroupBy,
  start: string,
  end: string,
): Record<string, string> {
  switch (groupBy) {
    case 'day':
      return { start: row.key, end: row.key }
    case 'cashier':
      return { start, end, cashier_id: row.key }
    case 'payment_method':
      return { start, end, payment_method_id: row.key }
    case 'category':
      return { start, end, category_id: row.key }
  }
}

export function SalesPage() {
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const [groupBy, setGroupBy] = useState<SalesGroupBy>('day')
  const query = { start, end, group_by: groupBy }
  const report = useQuery({
    ...reportsSalesOptions({ query }),
    placeholderData: keepPreviousData,
  })
  const data = report.data

  return (
    <>
      <ReportHeader
        title="Penjualan"
        description="Penjualan bersih dan laba kotor dalam satu periode. Struk yang dibatalkan tidak dihitung; retur dihitung pada hari terjadinya."
        excel={withQuery('reports/sales/excel', query)}
      />
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
        <Select
          value={groupBy}
          onValueChange={(value) => setGroupBy(value as SalesGroupBy)}
        >
          <SelectTrigger className="bg-card" aria-label="Kelompokkan">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(GROUPS) as SalesGroupBy[]).map((key) => (
              <SelectItem key={key} value={key}>
                {GROUPS[key].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Filters>

      {report.isError && (
        <p className="mt-6 text-destructive">{errorMessage(report.error)}</p>
      )}
      {data && (
        <div className="mt-4">
          <SalesTable
            title={GROUPS[data.group_by].title}
            total={data.total}
            lines={data.rows.map((row) => {
              const label =
                data.group_by === 'day' ? formatDate(row.key) : row.label
              const filter = receiptsOf(
                row,
                data.group_by,
                data.start,
                data.end,
              )
              return {
                key: row.key,
                label,
                figures: row,
                to: row.receipt_count
                  ? `/laporan/penjualan/struk?${new URLSearchParams({ ...filter, label })}`
                  : undefined,
              }
            })}
          />
          {data.rows.length === 0 && (
            <p className="mt-3 text-muted-foreground">
              Belum ada penjualan dalam periode ini.
            </p>
          )}
        </div>
      )}
    </>
  )
}
