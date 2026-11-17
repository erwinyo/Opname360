import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'

import type { SalesFigures } from '@/client'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { money, rupiah } from '@/lib/format'
import { cn } from '@/lib/utils'

export type SalesLine = {
  key: string
  label: ReactNode
  figures: SalesFigures
  // Where the row leads: the Receipts behind it.
  to?: string
}

type Column = {
  title: string
  value: (figures: SalesFigures) => ReactNode
  // Hidden on narrow screens.
  hide?: string
  strong?: boolean
}

function amount(value: number | string | null): ReactNode {
  if (value === null) return '—'
  return typeof value === 'number' ? rupiah(value) : money(value)
}

/** Net Sales and Gross Profit per row, with a total. Figures a grouping
 *  doesn't have (a Payment Method's COGS) are left out. */
export function SalesTable({
  title,
  lines,
  total,
}: {
  title: string
  lines: SalesLine[]
  total: SalesFigures
}) {
  const navigate = useNavigate()
  const parts = lines.some((line) => line.figures.gross_sales !== null)
  const costs = lines.some((line) => line.figures.cogs !== null)
  const columns: Column[] = [
    {
      title: 'Struk',
      value: (f) => f.receipt_count,
      hide: 'hidden md:table-cell',
    },
    ...(parts
      ? [
          {
            title: 'Penjualan kotor',
            value: (f: SalesFigures) => amount(f.gross_sales),
            hide: 'hidden lg:table-cell',
          },
          {
            title: 'Diskon',
            value: (f: SalesFigures) => amount(f.discounts),
            hide: 'hidden lg:table-cell',
          },
          {
            title: 'Retur',
            value: (f: SalesFigures) => amount(f.refunds),
            hide: 'hidden lg:table-cell',
          },
        ]
      : []),
    {
      title: 'Penjualan bersih',
      value: (f) => amount(f.net_sales),
      strong: true,
    },
    ...(costs
      ? [
          {
            title: 'HPP',
            value: (f: SalesFigures) => amount(f.cogs),
            hide: 'hidden md:table-cell',
          },
          {
            title: 'Laba kotor',
            value: (f: SalesFigures) => amount(f.gross_profit),
          },
        ]
      : []),
  ]

  return (
    <div className="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{title}</TableHead>
            {columns.map((column) => (
              <TableHead
                key={column.title}
                className={cn('text-right', column.hide)}
              >
                {column.title}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => (
            <TableRow
              key={line.key}
              className={cn(
                line.to && 'cursor-pointer',
                // Nothing happened: keep the busy rows in front.
                line.figures.receipt_count === 0 &&
                  !Number(line.figures.cogs) &&
                  'text-muted-foreground',
              )}
              onClick={line.to ? () => navigate(line.to ?? '') : undefined}
            >
              <TableCell>
                {line.to ? (
                  <Link
                    to={line.to}
                    className="font-medium"
                    onClick={(event) => event.stopPropagation()}
                  >
                    {line.label}
                  </Link>
                ) : (
                  line.label
                )}
              </TableCell>
              {columns.map((column) => (
                <TableCell
                  key={column.title}
                  className={cn(
                    'text-right whitespace-nowrap tabular-nums',
                    column.hide,
                    column.strong && 'font-medium',
                  )}
                >
                  {column.value(line.figures)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell className="font-semibold">Total</TableCell>
            {columns.map((column) => (
              <TableCell
                key={column.title}
                className={cn(
                  'text-right font-semibold whitespace-nowrap tabular-nums',
                  column.hide,
                )}
              >
                {column.value(total)}
              </TableCell>
            ))}
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  )
}
