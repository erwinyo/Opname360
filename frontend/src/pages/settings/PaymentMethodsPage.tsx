import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon, PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { PaymentMethodPublic } from '@/client'
import {
  paymentMethodsCreateMethodMutation,
  paymentMethodsListMethodsOptions,
  paymentMethodsListMethodsQueryKey,
  paymentMethodsUpdateMethodMutation,
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

const refresh = () =>
  queryClient.invalidateQueries({
    queryKey: paymentMethodsListMethodsQueryKey(),
  })

type OpenDialog =
  { kind: 'create' } | { kind: 'rename'; method: PaymentMethodPublic } | null

export function PaymentMethodsPage() {
  const methods = useQuery(paymentMethodsListMethodsOptions())
  const [dialog, setDialog] = useState<OpenDialog>(null)
  const setActive = useMutation({
    ...paymentMethodsUpdateMethodMutation(),
    onSuccess: (method) => {
      refresh()
      toast.success(
        `${method.name} ${method.is_active ? 'diaktifkan kembali' : 'dinonaktifkan'}.`,
      )
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Metode Pembayaran
          </h1>
          <p className="mt-1 text-muted-foreground">
            Pilihan pembayaran di kasir. Uang tunai masuk ke laci kas shift.
          </p>
        </div>
        <Button onClick={() => setDialog({ kind: 'create' })}>
          <PlusIcon />
          Tambah metode
        </Button>
      </div>

      {methods.isError && (
        <p className="mt-6 text-destructive">{errorMessage(methods.error)}</p>
      )}
      {methods.data && (
        <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nama</TableHead>
                <TableHead>Jenis</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-0">
                  <span className="sr-only">Tindakan</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {methods.data.map((method) => (
                <TableRow
                  key={method.id}
                  className={
                    method.is_active ? undefined : 'text-muted-foreground'
                  }
                >
                  <TableCell className="font-medium">{method.name}</TableCell>
                  <TableCell>
                    {method.is_cash ? 'Tunai, masuk laci kas' : 'Non-tunai'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={method.is_active ? 'secondary' : 'outline'}>
                      {method.is_active ? 'Aktif' : 'Nonaktif'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Tindakan untuk ${method.name}`}
                        >
                          <EllipsisIcon />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() => setDialog({ kind: 'rename', method })}
                        >
                          Ubah nama
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() =>
                            setActive.mutate({
                              path: { method_id: method.id },
                              body: { is_active: !method.is_active },
                            })
                          }
                        >
                          {method.is_active
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

      {dialog && (
        <MethodDialog
          method={dialog.kind === 'rename' ? dialog.method : undefined}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

function MethodDialog({
  method,
  onClose,
}: {
  method?: PaymentMethodPublic
  onClose: () => void
}) {
  const [name, setName] = useState(method?.name ?? '')
  const [isCash, setIsCash] = useState(false)
  const [checked, setChecked] = useState(false)
  const nameError = name.trim() ? undefined : 'Nama wajib diisi.'
  const onSuccess = (saved: PaymentMethodPublic) => {
    refresh()
    toast.success(`${saved.name} disimpan.`)
    onClose()
  }
  const create = useMutation({
    ...paymentMethodsCreateMethodMutation(),
    onSuccess,
  })
  const update = useMutation({
    ...paymentMethodsUpdateMethodMutation(),
    onSuccess,
  })
  const submit = () => {
    setChecked(true)
    if (nameError) return
    if (method) {
      update.mutate({ path: { method_id: method.id }, body: { name } })
    } else {
      create.mutate({ body: { name, is_cash: isCash } })
    }
  }

  return (
    <FormDialog
      title={method ? `Ubah ${method.name}` : 'Tambah metode pembayaran'}
      submitLabel="Simpan"
      pending={create.isPending || update.isPending}
      error={create.error ?? update.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="method-name"
        label="Nama"
        error={checked ? nameError : undefined}
      >
        <Input
          id="method-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={50}
          autoFocus
        />
      </Field>
      {!method && (
        <div className="flex items-start gap-3">
          <Switch
            id="method-cash"
            checked={isCash}
            onCheckedChange={setIsCash}
            className="mt-0.5"
          />
          <div>
            <Label htmlFor="method-cash">Tunai</Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Uangnya masuk ke laci kas dan dihitung saat tutup shift. Tidak
              bisa diubah setelah disimpan.
            </p>
          </div>
        </div>
      )}
    </FormDialog>
  )
}
