import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import type { Role, UserPublic } from '@/client'
import {
  usersCreateUserMutation,
  usersListUsersQueryKey,
  usersResetPasswordMutation,
  usersUpdateUserMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field, FormDialog } from '@/components/FormDialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { queryClient } from '@/lib/api'
import { ROLE_DESCRIPTIONS, ROLE_LABELS } from '@/lib/auth'

const ROLES: Role[] = ['owner', 'admin', 'cashier']
const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,50}$/
const USERNAME_RULE =
  '3–50 karakter: huruf, angka, titik, garis bawah, atau tanda hubung.'
const PASSWORD_RULE = 'Minimal 8 karakter.'

const refreshUsers = () =>
  queryClient.invalidateQueries({ queryKey: usersListUsersQueryKey() })

function RoleSelect({
  value,
  onChange,
}: {
  value: Role
  onChange: (role: Role) => void
}) {
  return (
    <Select value={value} onValueChange={(role) => onChange(role as Role)}>
      <SelectTrigger id="role" className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ROLES.map((role) => (
          <SelectItem key={role} value={role}>
            {ROLE_LABELS[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export function CreateUserDialog({ onClose }: { onClose: () => void }) {
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<Role>('cashier')
  const [password, setPassword] = useState('')
  const [checked, setChecked] = useState(false)

  const errors = {
    fullName: fullName.trim() ? undefined : 'Nama lengkap wajib diisi.',
    username: USERNAME_PATTERN.test(username) ? undefined : USERNAME_RULE,
    password: password.length >= 8 ? undefined : PASSWORD_RULE,
  }
  const create = useMutation({
    ...usersCreateUserMutation(),
    onSuccess: (user) => {
      refreshUsers()
      toast.success(`Akun ${user.username} dibuat.`)
      onClose()
    },
  })
  const submit = () => {
    setChecked(true)
    if (errors.fullName || errors.username || errors.password) return
    create.mutate({
      body: { full_name: fullName, username, role, password },
    })
  }

  return (
    <FormDialog
      title="Tambah pengguna"
      description="Berikan nama pengguna dan kata sandi ini kepada orangnya."
      submitLabel="Buat akun"
      pending={create.isPending}
      error={create.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="full-name"
        label="Nama lengkap"
        error={checked ? errors.fullName : undefined}
      >
        <Input
          id="full-name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          autoFocus
        />
      </Field>
      <Field
        id="username"
        label="Nama pengguna"
        hint="Dipakai untuk masuk. Huruf besar-kecil tidak dibedakan."
        error={checked ? errors.username : undefined}
      >
        <Input
          id="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoCapitalize="none"
          autoComplete="off"
        />
      </Field>
      <Field id="role" label="Peran" hint={ROLE_DESCRIPTIONS[role]}>
        <RoleSelect value={role} onChange={setRole} />
      </Field>
      <Field
        id="password"
        label="Kata sandi"
        hint={PASSWORD_RULE}
        error={checked ? errors.password : undefined}
      >
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
        />
      </Field>
    </FormDialog>
  )
}

export function EditUserDialog({
  user,
  onClose,
}: {
  user: UserPublic
  onClose: () => void
}) {
  const [fullName, setFullName] = useState(user.full_name)
  const [role, setRole] = useState<Role>(user.role)
  const [checked, setChecked] = useState(false)
  const nameError = fullName.trim() ? undefined : 'Nama lengkap wajib diisi.'

  const update = useMutation({
    ...usersUpdateUserMutation(),
    onSuccess: () => {
      refreshUsers()
      toast.success(`Akun ${user.username} diperbarui.`)
      onClose()
    },
  })
  const submit = () => {
    setChecked(true)
    if (nameError) return
    update.mutate({
      path: { user_id: user.id },
      body: { full_name: fullName, role },
    })
  }

  return (
    <FormDialog
      title={`Ubah ${user.username}`}
      submitLabel="Simpan"
      pending={update.isPending}
      error={update.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="full-name"
        label="Nama lengkap"
        error={checked ? nameError : undefined}
      >
        <Input
          id="full-name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          autoFocus
        />
      </Field>
      <Field id="role" label="Peran" hint={ROLE_DESCRIPTIONS[role]}>
        <RoleSelect value={role} onChange={setRole} />
      </Field>
    </FormDialog>
  )
}

export function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: UserPublic
  onClose: () => void
}) {
  const [password, setPassword] = useState('')
  const [checked, setChecked] = useState(false)
  const passwordError = password.length >= 8 ? undefined : PASSWORD_RULE

  const reset = useMutation({
    ...usersResetPasswordMutation(),
    onSuccess: () => {
      toast.success(`Kata sandi ${user.username} diganti.`)
      onClose()
    },
  })
  const submit = () => {
    setChecked(true)
    if (passwordError) return
    reset.mutate({ path: { user_id: user.id }, body: { password } })
  }

  return (
    <FormDialog
      title={`Atur ulang kata sandi ${user.username}`}
      description={`${user.full_name} akan keluar dari semua perangkat dan harus masuk lagi dengan kata sandi baru.`}
      submitLabel="Ganti kata sandi"
      pending={reset.isPending}
      error={reset.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="password"
        label="Kata sandi baru"
        hint={PASSWORD_RULE}
        error={checked ? passwordError : undefined}
      >
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          autoFocus
        />
      </Field>
    </FormDialog>
  )
}

export function DeactivateUserDialog({
  user,
  onClose,
}: {
  user: UserPublic
  onClose: () => void
}) {
  const deactivate = useMutation({
    ...usersUpdateUserMutation(),
    onSuccess: () => {
      refreshUsers()
      toast.success(`Akun ${user.username} dinonaktifkan.`)
      onClose()
    },
  })

  return (
    <FormDialog
      title={`Nonaktifkan ${user.username}?`}
      description={`${user.full_name} langsung keluar dan tidak bisa masuk lagi. Riwayat pekerjaannya tetap tersimpan, dan akun bisa diaktifkan kembali kapan saja.`}
      submitLabel="Nonaktifkan"
      destructive
      pending={deactivate.isPending}
      error={deactivate.error}
      onSubmit={() =>
        deactivate.mutate({
          path: { user_id: user.id },
          body: { is_active: false },
        })
      }
      onClose={onClose}
    />
  )
}
