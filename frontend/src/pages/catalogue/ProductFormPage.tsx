import { useMutation, useQuery } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  CopyIcon,
  HistoryIcon,
  PlusIcon,
  Trash2Icon,
} from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import type { ProductPublic, SkuPublic, SkuSave } from '@/client'
import {
  categoriesListCategoriesOptions,
  productsCreateProductMutation,
  productsDeleteProductMutation,
  productsListPriceChangesOptions,
  productsListProductsQueryKey,
  productsReadProductOptions,
  productsReadProductQueryKey,
  productsUpdateProductMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field, FormDialog } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { errorMessage, queryClient } from '@/lib/api'
import {
  formatDateTime,
  groupDigits,
  onlyDigits,
  quantity,
  rupiah,
  variantLabel,
} from '@/lib/format'

/** One SKU as typed in the form: everything is text until it is saved. */
type Row = {
  key: number
  id: number | null
  size: string
  color: string
  price: string
  unit: string
  barcode: string
  code: string
  packName: string
  packSize: string
  active: boolean
}

let nextKey = 1

const blankRow = (): Row => ({
  key: nextKey++,
  id: null,
  size: '',
  color: '',
  price: '',
  unit: 'pcs',
  barcode: '',
  code: '',
  packName: '',
  packSize: '',
  active: true,
})

const rowFromSku = (sku: SkuPublic): Row => ({
  key: nextKey++,
  id: sku.id,
  size: sku.size ?? '',
  color: sku.color ?? '',
  price: String(sku.selling_price),
  unit: sku.stock_unit,
  barcode: sku.barcode,
  code: sku.code,
  packName: sku.purchase_pack_name ?? '',
  packSize: sku.purchase_pack_size
    ? String(Number(sku.purchase_pack_size))
    : '',
  active: sku.is_active,
})

type RowErrors = { price?: string; unit?: string; pack?: string }

function checkRow(row: Row): RowErrors {
  const packSize = Number(row.packSize.replace(',', '.'))
  const hasName = row.packName.trim() !== ''
  const hasSize = row.packSize.trim() !== ''
  return {
    price: row.price === '' ? 'Harga jual wajib diisi.' : undefined,
    unit: row.unit.trim() ? undefined : 'Satuan wajib diisi.',
    pack:
      hasName !== hasSize
        ? 'Isi nama kemasan dan isinya, atau kosongkan keduanya.'
        : hasSize && !(packSize > 0)
          ? 'Isi kemasan harus angka lebih dari 0.'
          : undefined,
  }
}

const rowToSku = (row: Row): SkuSave => ({
  id: row.id,
  size: row.size,
  color: row.color,
  selling_price: Number(row.price),
  stock_unit: row.unit,
  barcode: row.barcode,
  code: row.code,
  purchase_pack_name: row.packName.trim() || null,
  purchase_pack_size: row.packSize.trim()
    ? row.packSize.trim().replace(',', '.')
    : null,
  is_active: row.active,
})

export function ProductFormPage() {
  const params = useParams()
  const productId = params.productId ? Number(params.productId) : null
  const product = useQuery({
    ...productsReadProductOptions({ path: { product_id: productId ?? 0 } }),
    enabled: productId !== null,
  })

  if (productId !== null && product.isPending) {
    return <p className="text-muted-foreground">Memuat…</p>
  }
  if (productId !== null && product.isError) {
    return (
      <>
        <BackLink />
        <p className="mt-4 text-destructive">{errorMessage(product.error)}</p>
      </>
    )
  }
  // Keyed, so opening another product starts from a fresh form.
  return <ProductForm key={productId ?? 'new'} product={product.data} />
}

function BackLink() {
  return (
    <Link
      to="/produk"
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeftIcon className="size-4" />
      Produk
    </Link>
  )
}

function ProductForm({ product }: { product?: ProductPublic }) {
  const navigate = useNavigate()
  const categories = useQuery(categoriesListCategoriesOptions())
  const [name, setName] = useState(product?.name ?? '')
  const [subCategoryId, setSubCategoryId] = useState(
    product ? String(product.sub_category_id) : '',
  )
  const [rows, setRows] = useState<Row[]>(
    product ? product.skus.map(rowFromSku) : [blankRow()],
  )
  const [checked, setChecked] = useState(false)
  const [historyOf, setHistoryOf] = useState<Row | null>(null)
  const [deleting, setDeleting] = useState(false)

  const errors = {
    name: name.trim() ? undefined : 'Nama produk wajib diisi.',
    subCategory: subCategoryId ? undefined : 'Pilih sub-kategori.',
  }
  const rowErrors = rows.map(checkRow)
  const invalid =
    Boolean(errors.name || errors.subCategory) ||
    rowErrors.some((e) => e.price || e.unit || e.pack)

  const onSaved = (saved: ProductPublic) => {
    queryClient.invalidateQueries({ queryKey: productsListProductsQueryKey() })
    queryClient.setQueryData(
      productsReadProductQueryKey({ path: { product_id: saved.id } }),
      saved,
    )
    toast.success(`Produk ${saved.name} disimpan.`)
    navigate('/produk')
  }
  const create = useMutation({
    ...productsCreateProductMutation(),
    onSuccess: onSaved,
  })
  const update = useMutation({
    ...productsUpdateProductMutation(),
    onSuccess: onSaved,
  })
  const saveError = create.error ?? update.error
  const saving = create.isPending || update.isPending

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (invalid) return
    const body = {
      name,
      sub_category_id: Number(subCategoryId),
      skus: rows.map(rowToSku),
    }
    if (product) {
      update.mutate({ path: { product_id: product.id }, body })
    } else {
      create.mutate({ body })
    }
  }

  const change = (key: number, patch: Partial<Row>) =>
    setRows((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    )
  const duplicate = (row: Row) =>
    setRows((current) => [
      ...current,
      { ...row, key: nextKey++, id: null, size: '', barcode: '', code: '' },
    ])
  const remove = (key: number) =>
    setRows((current) => current.filter((row) => row.key !== key))

  const noSubCategories =
    categories.data !== undefined &&
    categories.data.every((category) => category.sub_categories.length === 0)

  return (
    <>
    <form onSubmit={submit} noValidate>
      <BackLink />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        {product ? product.name : 'Produk baru'}
      </h1>

      <section className="mt-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2">
        <Field
          id="product-name"
          label="Nama produk"
          hint="Tanpa ukuran atau warna, misalnya Kemeja Putih SD."
          error={checked ? errors.name : undefined}
        >
          <Input
            id="product-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus={!product}
          />
        </Field>
        <Field
          id="sub-category"
          label="Sub-kategori"
          error={checked ? errors.subCategory : undefined}
        >
          <Select value={subCategoryId} onValueChange={setSubCategoryId}>
            <SelectTrigger id="sub-category" className="w-full">
              <SelectValue placeholder="Pilih sub-kategori" />
            </SelectTrigger>
            <SelectContent>
              {categories.data
                ?.filter((category) => category.sub_categories.length > 0)
                .map((category) => (
                  <SelectGroup key={category.id}>
                    <SelectLabel>{category.name}</SelectLabel>
                    {category.sub_categories.map((sub) => (
                      <SelectItem key={sub.id} value={String(sub.id)}>
                        {sub.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
            </SelectContent>
          </Select>
          {noSubCategories && (
            <p className="text-sm text-muted-foreground">
              Belum ada sub-kategori.{' '}
              <Link to="/kategori" className="text-primary underline">
                Buat di menu Kategori
              </Link>
              .
            </p>
          )}
        </Field>
      </section>

      <h2 className="mt-8 font-semibold">SKU</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Satu SKU untuk tiap ukuran atau warna yang dijual. Kosongkan barcode
        dan kode agar dibuatkan otomatis.
      </p>

      <div className="mt-3 grid gap-3">
        {rows.map((row, index) => {
          const error = checked ? rowErrors[index] : {}
          const label = variantLabel(row) || `SKU ${index + 1}`
          const id = (field: string) => `sku-${row.key}-${field}`
          return (
            <fieldset
              key={row.key}
              className="rounded-xl border bg-card p-4"
              aria-label={label}
            >
              <div className="grid grid-cols-2 gap-x-3 gap-y-4 md:grid-cols-4">
                <Field id={id('size')} label="Ukuran">
                  <Input
                    id={id('size')}
                    value={row.size}
                    onChange={(e) => change(row.key, { size: e.target.value })}
                  />
                </Field>
                <Field id={id('color')} label="Warna">
                  <Input
                    id={id('color')}
                    value={row.color}
                    onChange={(e) => change(row.key, { color: e.target.value })}
                  />
                </Field>
                <Field id={id('price')} label="Harga jual" error={error.price}>
                  <div className="relative">
                    <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">
                      Rp
                    </span>
                    <Input
                      id={id('price')}
                      value={groupDigits(row.price)}
                      onChange={(e) =>
                        change(row.key, { price: onlyDigits(e.target.value) })
                      }
                      inputMode="numeric"
                      className="pl-9 tabular-nums"
                    />
                  </div>
                </Field>
                <Field id={id('unit')} label="Satuan" error={error.unit}>
                  <Input
                    id={id('unit')}
                    value={row.unit}
                    onChange={(e) => change(row.key, { unit: e.target.value })}
                    list="stock-units"
                  />
                </Field>
                <Field
                  id={id('barcode')}
                  label="Barcode"
                  className="col-span-2 md:col-span-1"
                >
                  <Input
                    id={id('barcode')}
                    value={row.barcode}
                    onChange={(e) =>
                      change(row.key, { barcode: e.target.value })
                    }
                    placeholder="Otomatis"
                    className="tabular-nums"
                  />
                </Field>
                <Field id={id('code')} label="Kode">
                  <Input
                    id={id('code')}
                    value={row.code}
                    onChange={(e) => change(row.key, { code: e.target.value })}
                    placeholder="Otomatis"
                  />
                </Field>
                <Field id={id('pack-name')} label="Kemasan beli">
                  <Input
                    id={id('pack-name')}
                    value={row.packName}
                    onChange={(e) =>
                      change(row.key, { packName: e.target.value })
                    }
                    placeholder="mis. box"
                  />
                </Field>
                <Field id={id('pack-size')} label={`Isi (${row.unit || '…'})`}>
                  <Input
                    id={id('pack-size')}
                    value={row.packSize}
                    onChange={(e) =>
                      change(row.key, { packSize: e.target.value })
                    }
                    inputMode="decimal"
                    placeholder="mis. 12"
                    className="tabular-nums"
                  />
                </Field>
              </div>
              {error.pack && (
                <p className="mt-2 text-sm text-destructive">{error.pack}</p>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t pt-3">
                <span className="flex items-center gap-2">
                  <Switch
                    id={id('active')}
                    checked={row.active}
                    onCheckedChange={(active) => change(row.key, { active })}
                  />
                  <Label htmlFor={id('active')}>Dijual</Label>
                </span>
                <span className="ml-auto flex gap-1">
                  {row.id !== null && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setHistoryOf(row)}
                    >
                      <HistoryIcon />
                      Riwayat harga
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => duplicate(row)}
                  >
                    <CopyIcon />
                    Duplikat
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={rows.length === 1}
                    onClick={() => remove(row.key)}
                    aria-label={`Hapus ${label}`}
                  >
                    <Trash2Icon />
                    Hapus
                  </Button>
                </span>
              </div>
            </fieldset>
          )
        })}
      </div>
      <datalist id="stock-units">
        {['pcs', 'set', 'pasang', 'lusin', 'pak', 'box', 'rim', 'meter'].map(
          (unit) => (
            <option key={unit} value={unit} />
          ),
        )}
      </datalist>

      <Button
        type="button"
        variant="outline"
        className="mt-3"
        onClick={() => setRows((current) => [...current, blankRow()])}
      >
        <PlusIcon />
        Tambah SKU
      </Button>

      {saveError != null && (
        <p role="alert" className="mt-6 text-sm text-destructive">
          {errorMessage(saveError)}
        </p>
      )}
      {checked && invalid && (
        <p role="alert" className="mt-6 text-sm text-destructive">
          Masih ada isian yang perlu diperbaiki.
        </p>
      )}

      <div className="mt-6 flex flex-wrap gap-2 border-t pt-4">
        <Button type="submit" disabled={saving}>
          {saving ? 'Menyimpan…' : 'Simpan produk'}
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/produk">Batal</Link>
        </Button>
        {product && (
          <Button
            type="button"
            variant="ghost"
            className="ml-auto text-destructive hover:text-destructive"
            onClick={() => setDeleting(true)}
          >
            Hapus produk
          </Button>
        )}
      </div>

    </form>

      {/* Outside the form: a dialog's own submit would bubble into it. */}
      {historyOf?.id != null && (
        <PriceHistoryDialog
          skuId={historyOf.id}
          label={[product?.name, variantLabel(historyOf)]
            .filter(Boolean)
            .join(' · ')}
          onClose={() => setHistoryOf(null)}
        />
      )}
      {deleting && product && (
        <DeleteProductDialog
          product={product}
          onClose={() => setDeleting(false)}
        />
      )}
    </>
  )
}

function PriceHistoryDialog({
  skuId,
  label,
  onClose,
}: {
  skuId: number
  label: string
  onClose: () => void
}) {
  const changes = useQuery(
    productsListPriceChangesOptions({ path: { sku_id: skuId } }),
  )
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Riwayat harga jual</DialogTitle>
          <DialogDescription>{label}</DialogDescription>
        </DialogHeader>
        {changes.isPending && <p className="text-muted-foreground">Memuat…</p>}
        {changes.isError && (
          <p className="text-destructive">{errorMessage(changes.error)}</p>
        )}
        <ul className="grid gap-3">
          {changes.data?.map((change) => (
            <li key={change.id} className="flex items-baseline gap-3">
              <span className="font-medium tabular-nums">
                {change.old_price === null
                  ? rupiah(change.new_price)
                  : `${rupiah(change.old_price)} → ${rupiah(change.new_price)}`}
              </span>
              <span className="ml-auto text-right text-sm text-muted-foreground">
                {change.old_price === null ? 'Harga awal · ' : ''}
                {change.changed_by_name ?? 'Sistem'} ·{' '}
                {formatDateTime(change.changed_at)}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}

function DeleteProductDialog({
  product,
  onClose,
}: {
  product: ProductPublic
  onClose: () => void
}) {
  const navigate = useNavigate()
  const remove = useMutation({
    ...productsDeleteProductMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: productsListProductsQueryKey(),
      })
      toast.success(`Produk ${product.name} dihapus.`)
      navigate('/produk')
    },
  })
  const count = product.skus.length
  return (
    <FormDialog
      title={`Hapus ${product.name}?`}
      description={`Produk ini dan ${quantity(count)} SKU-nya akan dihapus.`}
      submitLabel="Hapus produk"
      destructive
      pending={remove.isPending}
      error={remove.error}
      onSubmit={() => remove.mutate({ path: { product_id: product.id } })}
      onClose={onClose}
    />
  )
}
