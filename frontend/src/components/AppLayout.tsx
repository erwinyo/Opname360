import { useMutation } from '@tanstack/react-query'
import { HouseIcon, LogOutIcon, MenuIcon, UsersIcon } from 'lucide-react'
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

const NAV: NavItem[] = [
  {
    to: '/',
    label: 'Beranda',
    icon: HouseIcon,
    roles: ['owner', 'admin', 'cashier'],
  },
  { to: '/pengguna', label: 'Pengguna', icon: UsersIcon, roles: ['owner'] },
]

export function AppLayout({ user }: { user: UserPublic }) {
  const items = NAV.filter((item) => item.roles.includes(user.role))
  const logout = useMutation({
    ...authLogoutMutation(),
    onSettled: () => setSignedInUser(null),
  })
  const signOut = () => logout.mutate({})

  return (
    <div className="min-h-svh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="sticky top-0 hidden h-svh flex-col border-r bg-sidebar md:flex">
        <Brand className="h-14 px-4" />
        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
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
            {items.map((item) => (
              <DropdownMenuItem key={item.to} asChild>
                <NavLink to={item.to}>
                  <item.icon />
                  {item.label}
                </NavLink>
              </DropdownMenuItem>
            ))}
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
