import { UsersIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { UserPublic } from '@/client'
import { ROLE_LABELS } from '@/lib/auth'

export function HomePage({ user }: { user: UserPublic }) {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">
        Halo, {user.full_name}
      </h1>
      <p className="mt-1 text-muted-foreground">
        Anda masuk sebagai {ROLE_LABELS[user.role]}.
      </p>

      {user.role === 'owner' ? (
        <Link
          to="/pengguna"
          className="mt-8 flex max-w-md items-center gap-4 rounded-xl border bg-card p-4 hover:border-primary/40"
        >
          <span className="grid size-10 place-items-center rounded-lg bg-sidebar-accent text-sidebar-accent-foreground">
            <UsersIcon className="size-5" />
          </span>
          <span>
            <span className="block font-medium">Pengguna</span>
            <span className="block text-sm text-muted-foreground">
              Buat akun untuk admin dan kasir.
            </span>
          </span>
        </Link>
      ) : (
        <p className="mt-8 max-w-md rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Belum ada menu untuk peran {ROLE_LABELS[user.role]}. Menu akan muncul
          di sini begitu tersedia.
        </p>
      )}
    </>
  )
}
