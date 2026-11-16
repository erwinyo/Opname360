import { useQuery } from '@tanstack/react-query'
import { ChevronRightIcon } from 'lucide-react'
import { Link } from 'react-router'

import { countingListSessionsOptions } from '@/client/@tanstack/react-query.gen'
import { errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

/** The sessions the signed-in user is a Checker in. */
export function CountingPage() {
  const sessions = useQuery(countingListSessionsOptions())

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-semibold tracking-tight">Hitung Stok</h1>
      <p className="mt-1 text-muted-foreground">
        Stok opname yang Anda ditugaskan menghitung.
      </p>
      {sessions.isError && (
        <p className="mt-6 text-destructive">{errorMessage(sessions.error)}</p>
      )}
      {sessions.data?.length === 0 && (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          Tidak ada opname untuk Anda saat ini.
        </p>
      )}
      <ul className="mt-6 grid gap-3">
        {sessions.data?.map((opname) => (
          <li key={opname.id}>
            <Link
              to={`/hitung/${opname.id}`}
              className="flex items-center gap-3 rounded-xl border bg-card p-4 hover:border-primary/40"
            >
              <span className="min-w-0 flex-1">
                <span className="block font-medium tabular-nums">
                  {opname.number}
                </span>
                <span className="block text-sm text-muted-foreground">
                  {opname.scope_label} · {opname.location_name}
                </span>
                <span className="block text-sm text-muted-foreground">
                  {opname.can_count
                    ? `Dibuka ${formatDateTime(opname.opened_at)}`
                    : 'Penghitungan ditutup, menunggu peninjauan'}
                </span>
              </span>
              <ChevronRightIcon className="size-5 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
