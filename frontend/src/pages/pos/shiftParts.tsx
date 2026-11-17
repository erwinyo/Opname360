import type { ShiftPublic } from '@/client'
import { Badge } from '@/components/ui/badge'
import { rupiah } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Counted minus expected cash, in words. */
export function CashVariance({ shift }: { shift: ShiftPublic }) {
  const variance = shift.cash_variance
  if (variance == null) {
    return <span className="text-muted-foreground">Masih terbuka</span>
  }
  return (
    <span
      className={cn(
        'tabular-nums',
        variance < 0 && 'font-medium text-destructive',
      )}
    >
      {variance === 0
        ? 'Sesuai'
        : `${variance > 0 ? 'Lebih' : 'Kurang'} ${rupiah(Math.abs(variance))}`}
    </span>
  )
}

/** Who bears a short drawer, or that the Owner still has to decide. */
export function ShiftDecision({ shift }: { shift: ShiftPublic }) {
  if (shift.needs_resolution) {
    return <Badge variant="destructive">Menunggu keputusan Pemilik</Badge>
  }
  if (shift.resolution === 'company_loss') return <>Kerugian perusahaan</>
  if (shift.resolution === 'employee_charge') {
    return <>Ganti rugi {shift.charged_user_name}</>
  }
  return <span className="text-muted-foreground">–</span>
}
