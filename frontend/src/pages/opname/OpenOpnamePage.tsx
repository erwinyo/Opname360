import { useMutation, useQuery } from '@tanstack/react-query'
import { XIcon } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import type { OpnameScope, SkuOption } from '@/client'
import {
  categoriesListCategoriesOptions,
  opnamesListStaffOptions,
  opnamesOpenOpnameMutation,
  opnamesOpeningAllowedOptions,
} from '@/client/@tanstack/react-query.gen'
import { BackLink } from '@/components/documents'
import { Field } from '@/components/FormDialog'
import { SkuFinder } from '@/components/SkuFinder'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/auth'
import { skuName } from '@/lib/format'
import { SCOPE_LABELS } from '@/lib/labels'

function toggle(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
}

function Check({
  checked,
  onChange,
  children,
}: {
  checked: boolean
  onChange: () => void
  children: ReactNode
}) {
  return (
    <label className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-md px-2 hover:bg-muted">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="size-4 accent-primary"
      />
      {children}
    </label>
  )
}

export function OpenOpnamePage() {
  const navigate = useNavigate()
  const categories = useQuery(categoriesListCategoriesOptions())
  const staff = useQuery(opnamesListStaffOptions())
  // Only before any stock has moved; after go-live the switch is noise.
  const openingAllowed = useQuery(opnamesOpeningAllowedOptions()).data === true
  const [opening, setOpening] = useState(false)
  const [scope, setScope] = useState<OpnameScope>('skus')
  const [categoryIds, setCategoryIds] = useState<number[]>([])
  const [subCategoryIds, setSubCategoryIds] = useState<number[]>([])
  const [skus, setSkus] = useState<SkuOption[]>([])
  const [checkerIds, setCheckerIds] = useState<number[]>([])
  const [note, setNote] = useState('')
  const [checked, setChecked] = useState(false)

  const effectiveScope = opening ? 'everything' : scope
  const scopeError =
    (effectiveScope === 'categories' && categoryIds.length === 0) ||
    (effectiveScope === 'sub_categories' && subCategoryIds.length === 0) ||
    (effectiveScope === 'skus' && skus.length === 0)
      ? 'Pilih apa yang dihitung.'
      : undefined
  const checkerError =
    checkerIds.length === 0 ? 'Pilih minimal satu checker.' : undefined

  const open = useMutation({
    ...opnamesOpenOpnameMutation(),
    onSuccess: (opname) => {
      toast.success(`Stok opname ${opname.number} dibuka.`)
      navigate(`/stok-opname/${opname.id}`)
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (scopeError || checkerError) return
    open.mutate({
      body: {
        scope: effectiveScope,
        category_ids: categoryIds,
        sub_category_ids: subCategoryIds,
        sku_ids: skus.map((sku) => sku.id),
        checker_ids: checkerIds,
        is_opening: opening,
        note: note.trim() || null,
      },
    })
  }

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl">
      <BackLink to="/stok-opname" label="Stok Opname" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        Buka stok opname
      </h1>
      <p className="mt-1 text-muted-foreground">
        Toko tetap buka. Checker menghitung tanpa melihat stok sistem, dan stok
        baru berubah setelah opname disetujui.
      </p>

      <section className="mt-6 grid gap-5 rounded-xl border bg-card p-4">
        {openingAllowed && (
          <div className="flex items-start gap-3">
            <Switch
              id="opening"
              checked={opening}
              onCheckedChange={setOpening}
              className="mt-0.5"
            />
            <div>
              <Label htmlFor="opening">Opname awal</Label>
              <p className="mt-1 text-sm text-muted-foreground">
                Sekali saja, sebelum ada mutasi stok: semua SKU dihitung, dan
                hasilnya menjadi stok awal dengan harga beli terakhir dari
                impor.
              </p>
            </div>
          </div>
        )}

        {!opening && (
          <Field
            id="scope"
            label="Yang dihitung"
            error={checked ? scopeError : undefined}
          >
            <Select
              value={scope}
              onValueChange={(value) => setScope(value as OpnameScope)}
            >
              <SelectTrigger id="scope" className="w-full sm:w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(SCOPE_LABELS) as OpnameScope[]).map((value) => (
                  <SelectItem key={value} value={value}>
                    {SCOPE_LABELS[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        )}

        {!opening && scope === 'categories' && (
          <fieldset className="grid gap-1 sm:grid-cols-2">
            <legend className="sr-only">Kategori</legend>
            {categories.data?.map((category) => (
              <Check
                key={category.id}
                checked={categoryIds.includes(category.id)}
                onChange={() =>
                  setCategoryIds((ids) => toggle(ids, category.id))
                }
              >
                {category.name}
              </Check>
            ))}
          </fieldset>
        )}

        {!opening && scope === 'sub_categories' && (
          <div className="grid gap-4 sm:grid-cols-2">
            {categories.data?.map((category) => (
              <fieldset key={category.id} className="grid gap-1">
                <legend className="mb-1 text-sm font-medium text-muted-foreground">
                  {category.name}
                </legend>
                {category.sub_categories.map((sub) => (
                  <Check
                    key={sub.id}
                    checked={subCategoryIds.includes(sub.id)}
                    onChange={() =>
                      setSubCategoryIds((ids) => toggle(ids, sub.id))
                    }
                  >
                    {sub.name}
                  </Check>
                ))}
              </fieldset>
            ))}
          </div>
        )}

        {!opening && scope === 'skus' && (
          <div>
            <SkuFinder
              onPick={(option) =>
                setSkus((picked) =>
                  picked.some((sku) => sku.id === option.id)
                    ? picked
                    : [...picked, option],
                )
              }
            />
            {skus.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-2">
                {skus.map((sku) => (
                  <li
                    key={sku.id}
                    className="flex items-center gap-1 rounded-full border bg-background py-0.5 pr-1 pl-3 text-sm"
                  >
                    {skuName(sku)}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-6 rounded-full"
                      aria-label={`Hapus ${skuName(sku)}`}
                      onClick={() =>
                        setSkus((picked) =>
                          picked.filter((other) => other.id !== sku.id),
                        )
                      }
                    >
                      <XIcon />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="mt-4 rounded-xl border bg-card p-4">
        <h2 className="font-medium">Checker</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Yang menghitung, dari HP masing-masing. Checker tidak bisa menyetujui
          opname ini.
        </p>
        {checked && checkerError && (
          <p className="mt-2 text-sm text-destructive">{checkerError}</p>
        )}
        <fieldset className="mt-3 grid gap-1 sm:grid-cols-2">
          <legend className="sr-only">Checker</legend>
          {staff.data?.map((user) => (
            <Check
              key={user.id}
              checked={checkerIds.includes(user.id)}
              onChange={() => setCheckerIds((ids) => toggle(ids, user.id))}
            >
              <span>
                {user.full_name}
                <span className="ml-2 text-sm text-muted-foreground">
                  {ROLE_LABELS[user.role]}
                </span>
              </span>
            </Check>
          ))}
        </fieldset>
      </section>

      <Field id="note" label="Catatan (opsional)" className="mt-4">
        <Textarea
          id="note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={500}
          className="bg-card"
        />
      </Field>

      {open.isError && (
        <p role="alert" className="mt-4 text-destructive">
          {errorMessage(open.error)}
        </p>
      )}
      <Button type="submit" className="mt-6" disabled={open.isPending}>
        {open.isPending ? 'Membuka…' : 'Buka opname'}
      </Button>
    </form>
  )
}
