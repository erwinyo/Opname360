import { LockIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { ShiftCurrent } from '@/client'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'

export function ShiftBar({ shift }: { shift: ShiftCurrent }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Kasir</h1>
        <p className="text-sm text-muted-foreground">
          Shift {shift.number} · {shift.cashier_name} · sejak{' '}
          {formatDateTime(shift.opened_at)}
        </p>
      </div>
      <Button asChild variant="outline">
        <Link to="/kasir/tutup">
          <LockIcon />
          Tutup shift
        </Link>
      </Button>
    </div>
  )
}
