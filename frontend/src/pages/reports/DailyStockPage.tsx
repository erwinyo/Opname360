import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { Link } from 'react-router'

import type { DailyStock } from '@/client'
import { reportsDailyStockOptions } from '@/client/@tanstack/react-query.gen'
import {
  CategoryFilter,
  DateInput,
  Empty,
  Filters,
  ReportHeader,
} from '@/components/reports'
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
import { money, quantity, skuName, today } from '@/lib/format'
import { ALL, chosen, withQuery } from '@/lib/reports'
import { cn } from '@/lib/utils'

type StockFlow = Pick<
  DailyStock,
  'opening' | 'quantity_in' | 'quantity_out' | 'closing' | 'closing_value'
>

export function DailyStockPage() {
  const [day, setDay] = useState(today)
  const [categoryId, setCategoryId] = useState(ALL)
  const [subCategoryId, setSubCategoryId] = useState(ALL)
  const query = {
    day,
    category_id: chosen(categoryId),
    sub_category_id: chosen(subCategoryId),
  }
  const report = useQuery({
    ...reportsDailyStockOptions({ query }),
    placeholderData: keepPreviousData,
  })
  const data = report.data

  return (
    <>
      <ReportHeader
        title="Laporan Stok Harian"
        description="Stok awal, masuk, keluar, dan akhir tiap SKU dalam satu hari, dengan nilai stok akhir."
        excel={withQuery('reports/daily-stock/excel', query)}
      />
      <Filters>
        <DateInput label="Tanggal" value={day} onChange={setDay} />
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
      {data && data.categories.length === 0 && (
        <Empty>Belum ada stok pada hari itu.</Empty>
      )}
      {data && data.categories.length > 0 && (
        <div className="mt-4 rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Barang</TableHead>
                <TableHead className="hidden text-right sm:table-cell">
                  Awal
                </TableHead>
                <TableHead className="hidden text-right sm:table-cell">
                  Masuk
                </TableHead>
                <TableHead className="hidden text-right sm:table-cell">
                  Keluar
                </TableHead>
                <TableHead className="text-right">Akhir</TableHead>
                <TableHead className="text-right">Nilai akhir</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.categories.map((category) => (
                <Fragment key={category.id}>
                  <GroupRow label={category.name} strong />
                  {category.sub_categories.map((sub) => (
                    <Fragment key={sub.id}>
                      <GroupRow label={sub.name} />
                      {sub.rows.map((row) => (
                        <TableRow key={row.sku_id}>
                          <TableCell className="pl-6">
                            <Link to={`/stok/${row.sku_id}`}>
                              {skuName(row)}
                            </Link>
                            <span className="block text-xs text-muted-foreground">
                              {row.code} · {row.stock_unit}
                            </span>
                            <FlowLine flow={row} />
                          </TableCell>
                          <FlowCells flow={row} />
                        </TableRow>
                      ))}
                      <TotalRow label={`Subtotal ${sub.name}`} flow={sub} />
                    </Fragment>
                  ))}
                  <TotalRow label={`Total ${category.name}`} flow={category} />
                </Fragment>
              ))}
            </TableBody>
            <TableFooter>
              <TotalRow label="Total" flow={data} />
            </TableFooter>
          </Table>
        </div>
      )}
    </>
  )
}

function GroupRow({ label, strong }: { label: string; strong?: boolean }) {
  return (
    <TableRow className="bg-muted/50 hover:bg-muted/50">
      <TableCell
        colSpan={6}
        className={cn(strong ? 'font-semibold' : 'pl-4 font-medium')}
      >
        {label}
      </TableCell>
    </TableRow>
  )
}

function TotalRow({ label, flow }: { label: string; flow: StockFlow }) {
  return (
    <TableRow className="font-medium">
      <TableCell>
        {label}
        <FlowLine flow={flow} />
      </TableCell>
      <FlowCells flow={flow} />
    </TableRow>
  )
}

/** On a phone, opening, in and out go under the name. */
function FlowLine({ flow }: { flow: StockFlow }) {
  return (
    <span className="block text-xs font-normal text-muted-foreground tabular-nums sm:hidden">
      Awal {quantity(flow.opening)} · masuk {quantity(flow.quantity_in)} ·
      keluar {quantity(flow.quantity_out)}
    </span>
  )
}

function FlowCells({ flow }: { flow: StockFlow }) {
  const closing = Number(flow.closing)
  return (
    <>
      {[flow.opening, flow.quantity_in, flow.quantity_out].map((value, i) => (
        <TableCell
          key={i}
          className="hidden text-right tabular-nums sm:table-cell"
        >
          {quantity(value)}
        </TableCell>
      ))}
      <TableCell
        className={cn(
          'text-right tabular-nums',
          closing < 0 && 'font-semibold text-destructive',
        )}
      >
        {quantity(flow.closing)}
      </TableCell>
      <TableCell className="text-right whitespace-nowrap tabular-nums">
        {money(flow.closing_value)}
      </TableCell>
    </>
  )
}
