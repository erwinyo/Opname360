import { useQuery } from '@tanstack/react-query'
import {
  BoxesIcon,
  ClipboardCheckIcon,
  PackageIcon,
  PackagePlusIcon,
  ScanBarcodeIcon,
  ShoppingCartIcon,
  TagsIcon,
  UsersIcon,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { Role, UserPublic } from '@/client'
import { countingListSessionsOptions } from '@/client/@tanstack/react-query.gen'
import { ROLE_LABELS } from '@/lib/auth'
import { Dashboard } from '@/pages/reports/Dashboard'

type Shortcut = {
  to: string
  title: string
  description: string
  icon: LucideIcon
  roles: Role[]
}

const SHORTCUTS: Shortcut[] = [
  {
    to: '/kasir',
    title: 'Kasir',
    description: 'Buka shift, jual, retur, dan tutup shift.',
    icon: ShoppingCartIcon,
    roles: ['owner', 'cashier'],
  },
  {
    to: '/stok-opname',
    title: 'Stok Opname',
    description: 'Buka opname, pantau penghitungan, tinjau selisih.',
    icon: ClipboardCheckIcon,
    roles: ['owner', 'admin'],
  },
  {
    to: '/stok',
    title: 'Stok',
    description: 'Jumlah dan nilai stok tiap SKU, dan kartu stoknya.',
    icon: BoxesIcon,
    roles: ['owner', 'admin'],
  },
  {
    to: '/barang-masuk',
    title: 'Barang Masuk',
    description: 'Catat barang yang diterima dari pemasok.',
    icon: PackagePlusIcon,
    roles: ['owner', 'admin'],
  },
  {
    to: '/produk',
    title: 'Produk',
    description: 'Daftar produk, SKU, barcode, dan harga jual.',
    icon: PackageIcon,
    roles: ['owner', 'admin'],
  },
  {
    to: '/kategori',
    title: 'Kategori',
    description: 'Kategori, sub-kategori, dan metode HPP.',
    icon: TagsIcon,
    roles: ['owner', 'admin'],
  },
  {
    to: '/pengguna',
    title: 'Pengguna',
    description: 'Buat akun untuk admin dan kasir.',
    icon: UsersIcon,
    roles: ['owner'],
  },
]

export function HomePage({ user }: { user: UserPublic }) {
  const shortcuts = SHORTCUTS.filter((item) => item.roles.includes(user.role))
  const counting = useQuery(countingListSessionsOptions())
  const toCount = counting.data?.filter((opname) => opname.can_count) ?? []
  return (
    <>
      {user.role === 'cashier' ? (
        <>
          <h1 className="text-2xl font-semibold tracking-tight">
            Halo, {user.full_name}
          </h1>
          <p className="mt-1 text-muted-foreground">
            Anda masuk sebagai {ROLE_LABELS[user.role]}.
          </p>
        </>
      ) : (
        <Dashboard />
      )}

      {toCount.length > 0 && (
        <div className="mt-6 grid gap-3">
          {toCount.map((opname) => (
            <Link
              key={opname.id}
              to={`/hitung/${opname.id}`}
              className="flex items-center gap-4 rounded-xl border border-primary/40 bg-primary/5 p-4 hover:border-primary"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
                <ScanBarcodeIcon className="size-5" />
              </span>
              <span>
                <span className="block font-medium">
                  Anda ditugaskan menghitung {opname.number}
                </span>
                <span className="block text-sm text-muted-foreground">
                  {opname.scope_label}. Ketuk untuk mulai menghitung.
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}

      {shortcuts.length > 0 ? (
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shortcuts.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="flex items-center gap-4 rounded-xl border bg-card p-4 hover:border-primary/40"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-sidebar-accent text-sidebar-accent-foreground">
                <item.icon className="size-5" />
              </span>
              <span>
                <span className="block font-medium">{item.title}</span>
                <span className="block text-sm text-muted-foreground">
                  {item.description}
                </span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-8 max-w-md rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
          Belum ada menu lain untuk peran {ROLE_LABELS[user.role]}. Saat Anda
          ditugaskan menghitung stok, tugasnya muncul di sini.
        </p>
      )}
    </>
  )
}
