import { LockIcon } from 'lucide-react'
import { Link, NavLink } from 'react-router'

import type { ShiftCurrent } from '@/client'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const SCREENS = [
  { to: '/kasir', label: 'Jual' },
  { to: '/kasir/retur', label: 'Retur / Tukar' },
  { to: '/kasir/transaksi', label: 'Transaksi' },
]

/** The open Shift, and the till's screens. */
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
      <div className="flex flex-wrap items-center gap-2">
        <nav className="flex rounded-lg border bg-card p-0.5">
          {SCREENS.map((screen) => (
            <NavLink
              key={screen.to}
              to={screen.to}
              end
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground',
                  isActive &&
                    'bg-primary text-primary-foreground hover:text-primary-foreground',
                )
              }
            >
              {screen.label}
            </NavLink>
          ))}
        </nav>
        <Button asChild variant="outline">
          <Link to="/kasir/tutup">
            <LockIcon />
            Tutup shift
          </Link>
        </Button>
      </div>
    </div>
  )
}
