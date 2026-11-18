import type { ReactNode } from 'react'

import type { StatementLine } from '@/client'
import { money } from '@/lib/format'
import { cn } from '@/lib/utils'

/** One group of a statement: its accounts and a total. */
export function StatementGroup({
  title,
  lines,
  total,
  totalLabel,
}: {
  title: string
  lines: StatementLine[]
  total: string
  totalLabel: string
}) {
  return (
    <section className="mt-4 first:mt-0">
      <h3 className="font-semibold">{title}</h3>
      <dl className="mt-1">
        {lines.map((line) => (
          <StatementRow
            key={`${line.account_id}-${line.name}`}
            label={line.name}
          >
            {money(line.amount)}
          </StatementRow>
        ))}
        {lines.length === 0 && (
          <StatementRow label="Tidak ada" muted>
            {money(0)}
          </StatementRow>
        )}
        <StatementRow label={totalLabel} strong>
          {money(total)}
        </StatementRow>
      </dl>
    </section>
  )
}

export function StatementRow({
  label,
  children,
  strong,
  muted,
}: {
  label: string
  children: ReactNode
  strong?: boolean
  muted?: boolean
}) {
  return (
    <div
      className={cn(
        'flex justify-between gap-4 py-1',
        strong ? 'border-t font-semibold' : 'pl-4',
        muted && 'text-muted-foreground',
      )}
    >
      <dt>{label}</dt>
      <dd className="text-right whitespace-nowrap tabular-nums">{children}</dd>
    </div>
  )
}
