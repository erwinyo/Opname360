import type { OpnameLinePublic, OpnameStatus } from '@/client'
import { Badge } from '@/components/ui/badge'
import { batchLabel, today } from '@/lib/format'
import { OPNAME_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** The Batch a medicine's line counts, red once it has expired. */
export function LineBatch({ line }: { line: OpnameLinePublic }) {
  if (!line.batch_number) return null
  const expired = Boolean(line.expires_on && line.expires_on < today())
  return (
    <span
      className={cn(
        'block text-sm font-medium tabular-nums',
        expired && 'text-destructive',
      )}
    >
      {batchLabel(line)}
    </span>
  )
}

export function OpnameStatusBadge({ status }: { status: OpnameStatus }) {
  const variant =
    status === 'approved'
      ? 'secondary'
      : status === 'cancelled' || status === 'reversed'
        ? 'destructive'
        : 'outline'
  return <Badge variant={variant}>{OPNAME_STATUS_LABELS[status]}</Badge>
}

/** A counted share as a bar, e.g. 12 of 40 lines counted. */
export function Progress({ done, total }: { done: number; total: number }) {
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)
  return (
    <div
      role="progressbar"
      aria-valuenow={done}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`${done} dari ${total} SKU sudah dihitung`}
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
    >
      <div
        className="h-full rounded-full bg-primary transition-[width]"
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}
