import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon, PencilIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { toast } from 'sonner'

import type {
  CategoryPublic,
  CostingMethod,
  SubCategoryPublic,
} from '@/client'
import {
  categoriesCreateCategoryMutation,
  categoriesCreateSubCategoryMutation,
  categoriesDeleteCategoryMutation,
  categoriesDeleteSubCategoryMutation,
  categoriesListCategoriesOptions,
  categoriesListCategoriesQueryKey,
  categoriesRenameSubCategoryMutation,
  categoriesUpdateCategoryMutation,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage, queryClient } from '@/lib/api'

const METHOD_LABELS: Record<CostingMethod, string> = {
  moving_average: 'Rata-rata',
  fifo: 'FIFO',
}
const METHOD_HINTS: Record<CostingMethod, string> = {
  moving_average:
    'HPP dihitung dari rata-rata harga beli semua stok yang ada.',
  fifo: 'Barang yang masuk lebih dulu dianggap terjual lebih dulu.',
}

const refresh = () =>
  queryClient.invalidateQueries({
    queryKey: categoriesListCategoriesQueryKey(),
  })

type OpenDialog =
  | { kind: 'create' }
  | { kind: 'edit' | 'delete'; category: CategoryPublic }
  | { kind: 'rename-sub' | 'delete-sub'; sub: SubCategoryPublic }
  | null

export function CategoriesPage() {
  const categories = useQuery(categoriesListCategoriesOptions())
  const [dialog, setDialog] = useState<OpenDialog>(null)
  const close = () => setDialog(null)

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Kategori</h1>
          <p className="mt-1 text-muted-foreground">
            Setiap produk masuk ke satu sub-kategori di dalam satu kategori.
          </p>
        </div>
        <Button onClick={() => setDialog({ kind: 'create' })}>
          <PlusIcon />
          Tambah kategori
        </Button>
      </div>

      {categories.isPending && (
        <p className="mt-6 text-muted-foreground">Memuat…</p>
      )}
      {categories.isError && (
        <p className="mt-6 text-destructive">
          {errorMessage(categories.error)}
        </p>
      )}
      {categories.data?.length === 0 && (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          Belum ada kategori. Mulai dengan kategori utama toko, misalnya
          Seragam atau ATK, lalu isi sub-kategorinya.
        </p>
      )}

      <div className="mt-6 grid items-start gap-4 lg:grid-cols-2">
        {categories.data?.map((category) => (
          <section key={category.id} className="rounded-xl border bg-card">
            <header className="flex items-center gap-2 border-b py-2 pr-2 pl-4">
              <h2 className="min-w-0 flex-1 truncate font-semibold">
                {category.name}
              </h2>
              <Badge variant="secondary">
                HPP {METHOD_LABELS[category.costing_method]}
              </Badge>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Tindakan untuk ${category.name}`}
                  >
                    <EllipsisIcon />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onSelect={() => setDialog({ kind: 'edit', category })}
                  >
                    Ubah kategori
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => setDialog({ kind: 'delete', category })}
                  >
                    Hapus kategori
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </header>
            <ul>
              {category.sub_categories.map((sub) => (
                <li
                  key={sub.id}
                  className="flex items-center gap-1 border-b py-1 pr-2 pl-4"
                >
                  <span className="min-w-0 flex-1 truncate">{sub.name}</span>
                  <span className="text-sm text-muted-foreground tabular-nums">
                    {sub.product_count} produk
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Ubah nama ${sub.name}`}
                    onClick={() => setDialog({ kind: 'rename-sub', sub })}
                  >
                    <PencilIcon />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Hapus ${sub.name}`}
                    onClick={() => setDialog({ kind: 'delete-sub', sub })}
                  >
                    <Trash2Icon />
                  </Button>
                </li>
              ))}
            </ul>
            <AddSubCategory category={category} />
          </section>
        ))}
      </div>

      {dialog?.kind === 'create' && <CategoryDialog onClose={close} />}
      {dialog?.kind === 'edit' && (
        <CategoryDialog category={dialog.category} onClose={close} />
      )}
      {dialog?.kind === 'delete' && (
        <DeleteCategoryDialog category={dialog.category} onClose={close} />
      )}
      {dialog?.kind === 'rename-sub' && (
        <RenameSubCategoryDialog sub={dialog.sub} onClose={close} />
      )}
      {dialog?.kind === 'delete-sub' && (
        <DeleteSubCategoryDialog sub={dialog.sub} onClose={close} />
      )}
    </>
  )
}

function AddSubCategory({ category }: { category: CategoryPublic }) {
  const [name, setName] = useState('')
  const add = useMutation({
    ...categoriesCreateSubCategoryMutation(),
    onSuccess: () => {
      refresh()
      setName('')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    add.mutate({ path: { category_id: category.id }, body: { name } })
  }
  return (
    <form onSubmit={submit} className="flex gap-2 p-2 pl-4">
      <Input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Sub-kategori baru"
        aria-label={`Sub-kategori baru di ${category.name}`}
      />
      <Button
        type="submit"
        variant="outline"
        disabled={add.isPending || !name.trim()}
        aria-label={`Tambah sub-kategori di ${category.name}`}
      >
        Tambah
      </Button>
    </form>
  )
}

function CategoryDialog({
  category,
  onClose,
}: {
  category?: CategoryPublic
  onClose: () => void
}) {
  const [name, setName] = useState(category?.name ?? '')
  const [method, setMethod] = useState<CostingMethod>(
    category?.costing_method ?? 'moving_average',
  )
  const [checked, setChecked] = useState(false)
  const nameError = name.trim() ? undefined : 'Nama kategori wajib diisi.'

  const onSuccess = () => {
    refresh()
    toast.success(`Kategori ${name.trim()} disimpan.`)
    onClose()
  }
  const create = useMutation({
    ...categoriesCreateCategoryMutation(),
    onSuccess,
  })
  const update = useMutation({
    ...categoriesUpdateCategoryMutation(),
    onSuccess,
  })
  const submit = () => {
    setChecked(true)
    if (nameError) return
    const body = { name, costing_method: method }
    if (category) {
      update.mutate({ path: { category_id: category.id }, body })
    } else {
      create.mutate({ body })
    }
  }

  return (
    <FormDialog
      title={category ? `Ubah ${category.name}` : 'Tambah kategori'}
      submitLabel="Simpan"
      pending={create.isPending || update.isPending}
      error={create.error ?? update.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="category-name"
        label="Nama kategori"
        error={checked ? nameError : undefined}
      >
        <Input
          id="category-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoFocus
        />
      </Field>
      <Field
        id="costing-method"
        label="Metode HPP"
        hint={METHOD_HINTS[method]}
      >
        <Select
          value={method}
          onValueChange={(value) => setMethod(value as CostingMethod)}
        >
          <SelectTrigger id="costing-method" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="moving_average">
              {METHOD_LABELS.moving_average}
            </SelectItem>
            <SelectItem value="fifo">{METHOD_LABELS.fifo}</SelectItem>
          </SelectContent>
        </Select>
      </Field>
    </FormDialog>
  )
}

function DeleteCategoryDialog({
  category,
  onClose,
}: {
  category: CategoryPublic
  onClose: () => void
}) {
  const remove = useMutation({
    ...categoriesDeleteCategoryMutation(),
    onSuccess: () => {
      refresh()
      toast.success(`Kategori ${category.name} dihapus.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Hapus kategori ${category.name}?`}
      description="Sub-kategorinya ikut terhapus. Kategori yang masih berisi produk tidak bisa dihapus."
      submitLabel="Hapus"
      destructive
      pending={remove.isPending}
      error={remove.error}
      onSubmit={() => remove.mutate({ path: { category_id: category.id } })}
      onClose={onClose}
    />
  )
}

function RenameSubCategoryDialog({
  sub,
  onClose,
}: {
  sub: SubCategoryPublic
  onClose: () => void
}) {
  const [name, setName] = useState(sub.name)
  const [checked, setChecked] = useState(false)
  const nameError = name.trim() ? undefined : 'Nama sub-kategori wajib diisi.'
  const rename = useMutation({
    ...categoriesRenameSubCategoryMutation(),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })
  const submit = () => {
    setChecked(true)
    if (nameError) return
    rename.mutate({ path: { sub_category_id: sub.id }, body: { name } })
  }
  return (
    <FormDialog
      title={`Ubah nama ${sub.name}`}
      submitLabel="Simpan"
      pending={rename.isPending}
      error={rename.error}
      onSubmit={submit}
      onClose={onClose}
    >
      <Field
        id="sub-category-name"
        label="Nama sub-kategori"
        error={checked ? nameError : undefined}
      >
        <Input
          id="sub-category-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoFocus
        />
      </Field>
    </FormDialog>
  )
}

function DeleteSubCategoryDialog({
  sub,
  onClose,
}: {
  sub: SubCategoryPublic
  onClose: () => void
}) {
  const remove = useMutation({
    ...categoriesDeleteSubCategoryMutation(),
    onSuccess: () => {
      refresh()
      toast.success(`Sub-kategori ${sub.name} dihapus.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Hapus sub-kategori ${sub.name}?`}
      description="Sub-kategori yang masih berisi produk tidak bisa dihapus."
      submitLabel="Hapus"
      destructive
      pending={remove.isPending}
      error={remove.error}
      onSubmit={() => remove.mutate({ path: { sub_category_id: sub.id } })}
      onClose={onClose}
    />
  )
}
