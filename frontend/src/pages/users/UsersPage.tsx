import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon, PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { UserPublic } from '@/client'
import {
  usersListUsersOptions,
  usersListUsersQueryKey,
  usersUpdateUserMutation,
} from '@/client/@tanstack/react-query.gen'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/auth'

import {
  CreateUserDialog,
  DeactivateUserDialog,
  EditUserDialog,
  ResetPasswordDialog,
} from './UserDialogs'

type OpenDialog =
  | { kind: 'create' }
  | { kind: 'edit' | 'password' | 'deactivate'; user: UserPublic }
  | null

export function UsersPage({ me }: { me: UserPublic }) {
  const users = useQuery(usersListUsersOptions())
  const [dialog, setDialog] = useState<OpenDialog>(null)
  const close = () => setDialog(null)

  const activate = useMutation({
    ...usersUpdateUserMutation(),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: usersListUsersQueryKey() })
      toast.success(`Akun ${user.username} diaktifkan kembali.`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pengguna</h1>
          <p className="mt-1 text-muted-foreground">
            Setiap orang masuk dengan akunnya sendiri.
          </p>
        </div>
        <Button onClick={() => setDialog({ kind: 'create' })}>
          <PlusIcon />
          Tambah pengguna
        </Button>
      </div>

      <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nama</TableHead>
              <TableHead className="hidden sm:table-cell">
                Nama pengguna
              </TableHead>
              <TableHead>Peran</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-0">
                <span className="sr-only">Tindakan</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.isPending && (
              <TableRow>
                <TableCell colSpan={5} className="text-muted-foreground">
                  Memuat…
                </TableCell>
              </TableRow>
            )}
            {users.isError && (
              <TableRow>
                <TableCell colSpan={5}>
                  <span className="text-destructive">
                    {errorMessage(users.error)}
                  </span>{' '}
                  <Button variant="link" onClick={() => users.refetch()}>
                    Coba lagi
                  </Button>
                </TableCell>
              </TableRow>
            )}
            {users.data?.map((user) => (
              <TableRow
                key={user.id}
                className={user.is_active ? undefined : 'text-muted-foreground'}
              >
                <TableCell>
                  <span className="font-medium">{user.full_name}</span>
                  {user.id === me.id && (
                    <span className="text-muted-foreground"> (Anda)</span>
                  )}
                  <span className="block text-sm text-muted-foreground sm:hidden">
                    {user.username}
                  </span>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {user.username}
                </TableCell>
                <TableCell>{ROLE_LABELS[user.role]}</TableCell>
                <TableCell>
                  <Badge variant={user.is_active ? 'secondary' : 'outline'}>
                    {user.is_active ? 'Aktif' : 'Nonaktif'}
                  </Badge>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Tindakan untuk ${user.username}`}
                      >
                        <EllipsisIcon />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onSelect={() => setDialog({ kind: 'edit', user })}
                      >
                        Ubah nama atau peran
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => setDialog({ kind: 'password', user })}
                      >
                        Atur ulang kata sandi
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      {user.is_active ? (
                        <DropdownMenuItem
                          variant="destructive"
                          onSelect={() =>
                            setDialog({ kind: 'deactivate', user })
                          }
                        >
                          Nonaktifkan
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onSelect={() =>
                            activate.mutate({
                              path: { user_id: user.id },
                              body: { is_active: true },
                            })
                          }
                        >
                          Aktifkan kembali
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {dialog?.kind === 'create' && <CreateUserDialog onClose={close} />}
      {dialog?.kind === 'edit' && (
        <EditUserDialog user={dialog.user} onClose={close} />
      )}
      {dialog?.kind === 'password' && (
        <ResetPasswordDialog user={dialog.user} onClose={close} />
      )}
      {dialog?.kind === 'deactivate' && (
        <DeactivateUserDialog user={dialog.user} onClose={close} />
      )}
    </>
  )
}
