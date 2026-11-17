import {
  BoxesIcon,
  ClipboardCheckIcon,
  CircleCheckIcon,
  Undo2Icon,
  WalletIcon,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { Attention } from '@/client'
import { rupiah } from '@/lib/format'

/** What the Owner should look at today. Every item says what and where. */
export function AttentionList({ attention }: { attention: Attention }) {
  const voids = attention.voids_today
  const items: {
    icon: LucideIcon
    to: string
    text: ReactNode
    more?: ReactNode
  }[] = []
  if (attention.negative_stock > 0) {
    items.push({
      icon: BoxesIcon,
      to: '/stok?minus=1',
      text: `${attention.negative_stock} SKU stok minus`,
    })
  }
  if (voids.length > 0) {
    items.push({
      icon: Undo2Icon,
      to: `/struk/${voids[0].id}`,
      text: `${voids.length} struk dibatalkan hari ini`,
      more: (
        <ul className="mt-1 grid gap-0.5 text-sm text-muted-foreground">
          {voids.slice(0, 5).map((void_) => (
            <li key={void_.id}>
              <Link
                to={`/struk/${void_.id}`}
                className="tabular-nums underline-offset-2 hover:underline"
              >
                {void_.number}
              </Link>{' '}
              · {rupiah(void_.total)} · {void_.cashier_name}
              {void_.reason ? `: ${void_.reason}` : ''}
            </li>
          ))}
        </ul>
      ),
    })
  }
  if (attention.opnames_waiting > 0) {
    items.push({
      icon: ClipboardCheckIcon,
      to: '/stok-opname?status=review',
      text: `${attention.opnames_waiting} stok opname menunggu persetujuan`,
    })
  }
  if (attention.shifts_waiting > 0) {
    items.push({
      icon: WalletIcon,
      to: '/shift?menunggu=1',
      text: `${attention.shifts_waiting} shift dengan kas kurang menunggu keputusan`,
    })
  }

  return (
    <section className="mt-3 rounded-xl border bg-card p-4">
      <h2 className="font-medium">Perlu perhatian</h2>
      {items.length === 0 ? (
        <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
          <CircleCheckIcon className="size-4" />
          Tidak ada yang perlu ditindaklanjuti.
        </p>
      ) : (
        <ul className="mt-2 grid gap-3" aria-label="Perlu perhatian">
          {items.map((item) => (
            <li key={item.to} className="flex gap-3">
              <item.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <Link
                  to={item.to}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  {item.text}
                </Link>
                {item.more}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
