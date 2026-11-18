import { useMutation } from '@tanstack/react-query'
import {
  ArrowLeftRightIcon,
  BanknoteArrowDownIcon,
  BookOpenIcon,
  BoxesIcon,
  CalendarDaysIcon,
  ChartColumnStackedIcon,
  ChartPieIcon,
  ClipboardCheckIcon,
  CreditCardIcon,
  FlagIcon,
  GaugeIcon,
  HandCoinsIcon,
  HistoryIcon,
  HouseIcon,
  ListChecksIcon,
  ListTreeIcon,
  LogOutIcon,
  MenuIcon,
  NotebookPenIcon,
  PackageIcon,
  PackagePlusIcon,
  PercentIcon,
  PrinterIcon,
  ReceiptTextIcon,
  ScaleIcon,
  ScanBarcodeIcon,
  ScissorsIcon,
  ShoppingCartIcon,
  SlidersHorizontalIcon,
  StoreIcon,
  TagsIcon,
  TrendingUpIcon,
  TruckIcon,
  Undo2Icon,
  UsersIcon,
  WalletIcon,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import type { Role, UserPublic } from '@/client'
import { authLogoutMutation } from '@/client/@tanstack/react-query.gen'
import { Brand } from '@/components/Brand'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { setSignedInUser } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/auth'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon; roles: Role[] }
type NavGroup = { label?: string; items: NavItem[] }

const BACK_OFFICE: Role[] = ['owner', 'admin']
const TILL: Role[] = ['owner', 'cashier']

const NAV: NavGroup[] = [
  {
    items: [
      { to: '/', label: 'Dasbor', icon: GaugeIcon, roles: BACK_OFFICE },
      { to: '/', label: 'Beranda', icon: HouseIcon, roles: ['cashier'] },
      { to: '/kasir', label: 'Kasir', icon: ShoppingCartIcon, roles: TILL },
      {
        to: '/hitung',
        label: 'Hitung Stok',
        icon: ScanBarcodeIcon,
        roles: ['owner', 'admin', 'cashier'],
      },
    ],
  },
  {
    label: 'Laporan',
    items: [
      {
        to: '/laporan/penjualan',
        label: 'Penjualan',
        icon: ReceiptTextIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/laporan/laba-kotor',
        label: 'Laba Kotor per Jam',
        icon: ChartColumnStackedIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/laporan/fast-moving',
        label: 'Fast Moving',
        icon: TrendingUpIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/laporan/kontribusi-omzet',
        label: 'Kontribusi Omzet',
        icon: ChartPieIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/laporan/stok-harian',
        label: 'Stok Harian',
        icon: CalendarDaysIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/laporan/selisih-opname',
        label: 'Selisih Opname',
        icon: ScaleIcon,
        roles: BACK_OFFICE,
      },
    ],
  },
  {
    label: 'Pembukuan',
    items: [
      {
        to: '/jurnal',
        label: 'Jurnal',
        icon: NotebookPenIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/buku-besar',
        label: 'Buku Besar',
        icon: BookOpenIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/neraca-saldo',
        label: 'Neraca Saldo',
        icon: ListChecksIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/kas-keluar',
        label: 'Kas Keluar',
        icon: BanknoteArrowDownIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/pindah-kas',
        label: 'Pindah Kas',
        icon: ArrowLeftRightIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/bayar-hutang',
        label: 'Bayar Hutang',
        icon: HandCoinsIcon,
        roles: BACK_OFFICE,
      },
      { to: '/akun', label: 'Akun', icon: ListTreeIcon, roles: BACK_OFFICE },
      {
        to: '/saldo-awal',
        label: 'Saldo Awal',
        icon: FlagIcon,
        roles: ['owner'],
      },
    ],
  },
  {
    label: 'Penjualan',
    items: [
      { to: '/shift', label: 'Shift', icon: WalletIcon, roles: BACK_OFFICE },
      { to: '/promo', label: 'Promo', icon: PercentIcon, roles: BACK_OFFICE },
    ],
  },
  {
    label: 'Stok',
    items: [
      { to: '/stok', label: 'Stok', icon: BoxesIcon, roles: BACK_OFFICE },
      {
        to: '/stok-opname',
        label: 'Stok Opname',
        icon: ClipboardCheckIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/ganti-rugi',
        label: 'Ganti Rugi Karyawan',
        icon: HandCoinsIcon,
        roles: ['owner'],
      },
      {
        to: '/barang-masuk',
        label: 'Barang Masuk',
        icon: PackagePlusIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/hasil-produksi',
        label: 'Hasil Produksi',
        icon: ScissorsIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/retur-pembelian',
        label: 'Retur Pembelian',
        icon: Undo2Icon,
        roles: BACK_OFFICE,
      },
    ],
  },
  {
    label: 'Katalog',
    items: [
      { to: '/produk', label: 'Produk', icon: PackageIcon, roles: BACK_OFFICE },
      {
        to: '/kategori',
        label: 'Kategori',
        icon: TagsIcon,
        roles: BACK_OFFICE,
      },
      {
        to: '/label',
        label: 'Cetak Label',
        icon: PrinterIcon,
        roles: BACK_OFFICE,
      },
      { to: '/pemasok', label: 'Pemasok', icon: TruckIcon, roles: BACK_OFFICE },
    ],
  },
  {
    label: 'Pengaturan',
    items: [
      { to: '/pengguna', label: 'Pengguna', icon: UsersIcon, roles: ['owner'] },
      {
        to: '/log-aktivitas',
        label: 'Log Aktivitas',
        icon: HistoryIcon,
        roles: ['owner'],
      },
      {
        to: '/pengaturan-toko',
        label: 'Pengaturan Toko',
        icon: StoreIcon,
        roles: ['owner'],
      },
      {
        to: '/metode-pembayaran',
        label: 'Metode Pembayaran',
        icon: CreditCardIcon,
        roles: ['owner'],
      },
      {
        to: '/pengaturan-akun',
        label: 'Pengaturan Akun',
        icon: SlidersHorizontalIcon,
        roles: ['owner'],
      },
    ],
  },
]

export function AppLayout({ user }: { user: UserPublic }) {
  const groups = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.roles.includes(user.role)),
  })).filter((group) => group.items.length > 0)
  const logout = useMutation({
    ...authLogoutMutation(),
    onSettled: () => setSignedInUser(null),
  })
  const signOut = () => logout.mutate({})

  return (
    <div className="min-h-svh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="sticky top-0 hidden h-svh flex-col border-r bg-sidebar md:flex">
        <Brand className="h-14 px-4" />
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {groups.map((group) => (
            <div key={group.label ?? 'top'} className="mb-3 grid gap-0.5">
              {group.label && (
                <p className="px-2.5 pt-2 pb-1 text-xs font-medium text-muted-foreground">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                      isActive &&
                        'bg-sidebar-accent text-sidebar-accent-foreground',
                    )
                  }
                >
                  <item.icon className="size-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="flex items-center gap-2 border-t p-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user.full_name}</p>
            <p className="text-xs text-muted-foreground">
              {ROLE_LABELS[user.role]}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={signOut}
            aria-label="Keluar"
            title="Keluar"
          >
            <LogOutIcon />
          </Button>
        </div>
      </aside>

      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background px-4 md:hidden">
        <Brand />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Menu">
              <MenuIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              {user.full_name}
              <span className="block text-xs font-normal text-muted-foreground">
                {ROLE_LABELS[user.role]}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {groups.flatMap((group) =>
              group.items.map((item) => (
                <DropdownMenuItem key={item.to} asChild>
                  <NavLink to={item.to}>
                    <item.icon />
                    {item.label}
                  </NavLink>
                </DropdownMenuItem>
              )),
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={signOut}>
              <LogOutIcon />
              Keluar
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <main className="min-w-0 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
