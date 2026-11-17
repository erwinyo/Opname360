import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon, PlusIcon } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { AccountPublic, AccountType } from '@/client'
import {
  ledgerCreateAccountMutation,
  ledgerDeleteAccountMutation,
  ledgerListAccountsOptions,
  ledgerListAccountsQueryKey,
  ledgerUpdateAccountMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field, FormDialog } from '@/components/FormDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'
import { money } from '@/lib/format'
import { ACCOUNT_TYPE_LABELS } from '@/lib/labels'

const refresh = () =>
  queryClient.invalidateQueries({ queryKey: ledgerListAccountsQueryKey() })

type Dialog =
  | { kind: 'edit'; account?: AccountPublic }
  | { kind: 'delete'; account: AccountPublic }
  | null

/** The chart of accounts, by type, with each account's balance. */
export function AccountsPage() {
  const accounts = useQuery(ledgerListAccountsOptions())
  const [dialog, setDialog] = useState<Dialog>(null)
  const types = Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[]

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Akun</h1>
          <p className="mt-1 text-muted-foreground">
            Daftar akun pembukuan. Akun bertanda Sistem diisi otomatis dari
            dokumen dan tidak bisa dihapus.
          </p>
        </div>
        <Button onClick={() => setDialog({ kind: 'edit' })}>
          <PlusIcon />
          Tambah akun
        </Button>
      </div>
      {accounts.isError && (
        <p className="mt-6 text-destructive">{errorMessage(accounts.error)}</p>
      )}
      {accounts.data && (
        <div className="mt-6 rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Kode</TableHead>
                <TableHead>Nama</TableHead>
                <TableHead className="text-right">Saldo</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Tindakan</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {types.map((type) => (
                <Fragment key={type}>
                  <TableRow className="bg-muted/50 hover:bg-muted/50">
                    <TableCell colSpan={4} className="font-semibold">
                      {ACCOUNT_TYPE_LABELS[type]}
                    </TableCell>
                  </TableRow>
                  {accounts.data
                    .filter((account) => account.type === type)
                    .map((account) => (
                      <TableRow
                        key={account.id}
                        className={
                          account.is_active
                            ? undefined
                            : 'text-muted-foreground'
                        }
                      >
                        <TableCell className="tabular-nums">
                          {account.code}
                        </TableCell>
                        <TableCell>
                          <Link
                            to={`/buku-besar?akun=${account.id}`}
                            className="font-medium"
                          >
                            {account.name}
                          </Link>
                          <span className="ml-2 inline-flex gap-1">
                            {account.role && (
                              <Badge variant="secondary">Sistem</Badge>
                            )}
                            {account.is_cash && (
                              <Badge variant="outline">Kas/Bank</Badge>
                            )}
                            {!account.is_active && (
                              <Badge variant="outline">Nonaktif</Badge>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">
                          {money(account.balance)}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`Tindakan untuk ${account.name}`}
                              >
                                <EllipsisIcon />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onSelect={() =>
                                  setDialog({ kind: 'edit', account })
                                }
                              >
                                Ubah
                              </DropdownMenuItem>
                              {!account.role && !account.used && (
                                <DropdownMenuItem
                                  onSelect={() =>
                                    setDialog({ kind: 'delete', account })
                                  }
                                >
                                  Hapus
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {dialog?.kind === 'edit' && (
        <AccountDialog
          account={dialog.account}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'delete' && (
        <DeleteDialog
          account={dialog.account}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

function AccountDialog({
  account,
  onClose,
}: {
  account?: AccountPublic
  onClose: () => void
}) {
  const [code, setCode] = useState(account?.code ?? '')
  const [name, setName] = useState(account?.name ?? '')
  const [type, setType] = useState<AccountType>(account?.type ?? 'expense')
  const [isCash, setIsCash] = useState(account?.is_cash ?? false)
  const [isActive, setIsActive] = useState(account?.is_active ?? true)
  const [checked, setChecked] = useState(false)
  const system = Boolean(account?.role)
  const errors = {
    code: code.trim() ? undefined : 'Kode wajib diisi.',
    name: name.trim() ? undefined : 'Nama wajib diisi.',
  }
  const onSuccess = (saved: AccountPublic) => {
    refresh()
    toast.success(`Akun ${saved.code} ${saved.name} disimpan.`)
    onClose()
  }
  const create = useMutation({ ...ledgerCreateAccountMutation(), onSuccess })
  const update = useMutation({ ...ledgerUpdateAccountMutation(), onSuccess })
  const submit = () => {
    setChecked(true)
    if (errors.code || errors.name) return
    const body = {
      code,
      name,
      type,
      is_cash: type === 'asset' && isCash,
      is_active: isActive,
    }
    if (account) {
      update.mutate({ path: { account_id: account.id }, body })
    } else {
      create.mutate({ body })
    }
  }

  return (
    <FormDialog
      title={account ? `Ubah ${account.name}` : 'Tambah akun'}
      description={
        system
          ? 'Akun ini dipakai sistem: hanya kode dan namanya yang bisa diubah.'
          : undefined
      }
      submitLabel="Simpan"
      pending={create.isPending || update.isPending}
      error={create.error ?? update.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <div className="grid grid-cols-[8rem_1fr] gap-3">
        <Field
          id="account-code"
          label="Kode"
          error={checked ? errors.code : undefined}
        >
          <Input
            id="account-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            maxLength={20}
            autoFocus
          />
        </Field>
        <Field
          id="account-name"
          label="Nama"
          error={checked ? errors.name : undefined}
        >
          <Input
            id="account-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
          />
        </Field>
      </div>
      {!system && (
        <>
          <Field id="account-type" label="Jenis">
            <Select
              value={type}
              onValueChange={(value) => setType(value as AccountType)}
              disabled={account?.used}
            >
              <SelectTrigger id="account-type" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[]).map(
                  (key) => (
                    <SelectItem key={key} value={key}>
                      {ACCOUNT_TYPE_LABELS[key]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </Field>
          {type === 'asset' && (
            <div className="flex items-center gap-3">
              <Switch
                id="account-cash"
                checked={isCash}
                onCheckedChange={setIsCash}
              />
              <Label htmlFor="account-cash">
                Akun kas atau bank (uang bisa dibayar dari sini)
              </Label>
            </div>
          )}
          <div className="flex items-center gap-3">
            <Switch
              id="account-active"
              checked={isActive}
              onCheckedChange={setIsActive}
            />
            <Label htmlFor="account-active">Aktif</Label>
          </div>
        </>
      )}
    </FormDialog>
  )
}

function DeleteDialog({
  account,
  onClose,
}: {
  account: AccountPublic
  onClose: () => void
}) {
  const remove = useMutation({
    ...ledgerDeleteAccountMutation(),
    onSuccess: () => {
      refresh()
      toast.success(`Akun ${account.name} dihapus.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Hapus akun ${account.name}?`}
      description="Akun ini belum pernah dipakai, jadi bisa dihapus."
      submitLabel="Hapus"
      destructive
      pending={remove.isPending}
      error={remove.error}
      onSubmit={() => remove.mutate({ path: { account_id: account.id } })}
      onClose={onClose}
    />
  )
}
