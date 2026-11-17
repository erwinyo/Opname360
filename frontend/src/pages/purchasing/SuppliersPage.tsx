import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon, PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { SupplierPublic } from '@/client'
import {
  suppliersCreateSupplierMutation,
  suppliersListSuppliersOptions,
  suppliersListSuppliersQueryKey,
  suppliersUpdateSupplierMutation,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'

const refresh = () =>
  queryClient.invalidateQueries({ queryKey: suppliersListSuppliersQueryKey() })

type OpenDialog =
  { kind: 'create' } | { kind: 'edit'; supplier: SupplierPublic } | null

export function SuppliersPage() {
  const suppliers = useQuery(suppliersListSuppliersOptions())
  const [dialog, setDialog] = useState<OpenDialog>(null)
  const setActive = useMutation({
    ...suppliersUpdateSupplierMutation(),
    onSuccess: (supplier) => {
      refresh()
      toast.success(
        `Pemasok ${supplier.name} ${supplier.is_active ? 'diaktifkan kembali' : 'dinonaktifkan'}.`,
      )
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pemasok</h1>
          <p className="mt-1 text-muted-foreground">
            Dari siapa toko membeli barang.
          </p>
        </div>
        <Button onClick={() => setDialog({ kind: 'create' })}>
          <PlusIcon />
          Tambah pemasok
        </Button>
      </div>

      {suppliers.isError && (
        <p className="mt-6 text-destructive">{errorMessage(suppliers.error)}</p>
      )}
      {suppliers.data?.length === 0 && (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          Belum ada pemasok. Tambahkan pemasok sebelum mencatat barang masuk.
        </p>
      )}
      {suppliers.data && suppliers.data.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nama</TableHead>
                <TableHead>Telepon</TableHead>
                <TableHead className="hidden md:table-cell">Alamat</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Tindakan</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {suppliers.data.map((supplier) => (
                <TableRow
                  key={supplier.id}
                  className={
                    supplier.is_active ? undefined : 'text-muted-foreground'
                  }
                >
                  <TableCell className="font-medium">{supplier.name}</TableCell>
                  <TableCell>{supplier.phone ?? '–'}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {supplier.address ?? '–'}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={supplier.is_active ? 'secondary' : 'outline'}
                    >
                      {supplier.is_active ? 'Aktif' : 'Nonaktif'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Tindakan untuk ${supplier.name}`}
                        >
                          <EllipsisIcon />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() => setDialog({ kind: 'edit', supplier })}
                        >
                          Ubah
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() =>
                            setActive.mutate({
                              path: { supplier_id: supplier.id },
                              body: { is_active: !supplier.is_active },
                            })
                          }
                        >
                          {supplier.is_active
                            ? 'Nonaktifkan'
                            : 'Aktifkan kembali'}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {dialog?.kind === 'create' && (
        <SupplierDialog onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'edit' && (
        <SupplierDialog
          supplier={dialog.supplier}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

export function SupplierDialog({
  supplier,
  onClose,
  onSaved,
}: {
  supplier?: SupplierPublic
  onClose: () => void
  onSaved?: (supplier: SupplierPublic) => void
}) {
  const [name, setName] = useState(supplier?.name ?? '')
  const [phone, setPhone] = useState(supplier?.phone ?? '')
  const [address, setAddress] = useState(supplier?.address ?? '')
  const [checked, setChecked] = useState(false)
  const nameError = name.trim() ? undefined : 'Nama pemasok wajib diisi.'

  const onSuccess = (saved: SupplierPublic) => {
    refresh()
    toast.success(`Pemasok ${saved.name} disimpan.`)
    onSaved?.(saved)
    onClose()
  }
  const create = useMutation({
    ...suppliersCreateSupplierMutation(),
    onSuccess,
  })
  const update = useMutation({
    ...suppliersUpdateSupplierMutation(),
    onSuccess,
  })
  const submit = () => {
    setChecked(true)
    if (nameError) return
    const body = { name, phone, address }
    if (supplier) {
      update.mutate({ path: { supplier_id: supplier.id }, body })
    } else {
      create.mutate({ body })
    }
  }

  return (
    <FormDialog
      title={supplier ? `Ubah ${supplier.name}` : 'Tambah pemasok'}
      submitLabel="Simpan"
      pending={create.isPending || update.isPending}
      error={create.error ?? update.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="supplier-name"
        label="Nama pemasok"
        error={checked ? nameError : undefined}
      >
        <Input
          id="supplier-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoFocus
        />
      </Field>
      <Field id="supplier-phone" label="Telepon">
        <Input
          id="supplier-phone"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          inputMode="tel"
        />
      </Field>
      <Field id="supplier-address" label="Alamat">
        <Input
          id="supplier-address"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
        />
      </Field>
    </FormDialog>
  )
}
