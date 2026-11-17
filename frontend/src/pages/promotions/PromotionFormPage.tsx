import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import type { DiscountKind, PromotionPublic, TargetKind } from '@/client'
import {
  categoriesListCategoriesOptions,
  promotionsCreatePromotionMutation,
  promotionsListPromotionsQueryKey,
  promotionsReadPromotionOptions,
  promotionsUpdatePromotionMutation,
} from '@/client/@tanstack/react-query.gen'
import {
  CategoryChecks,
  Chips,
  SubCategoryChecks,
} from '@/components/CatalogueChecks'
import { BackLink } from '@/components/documents'
import { Field } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { SkuFinder } from '@/components/SkuFinder'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage, queryClient } from '@/lib/api'
import { skuName, toLocalInput } from '@/lib/format'
import { TARGET_KIND_LABELS } from '@/lib/labels'
import { toggle } from '@/lib/utils'

type Picked = { id: number; label: string }

/** Create a Promotion, or change one no Receipt has used yet. */
export function PromotionFormPage() {
  const promotionId = Number(useParams().promotionId) || null
  const promotion = useQuery({
    ...promotionsReadPromotionOptions({
      path: { promotion_id: promotionId ?? 0 },
    }),
    enabled: promotionId !== null,
  })
  if (promotionId !== null && promotion.isPending) {
    return <p className="text-muted-foreground">Memuat…</p>
  }
  if (promotion.isError) {
    return <p className="text-destructive">{errorMessage(promotion.error)}</p>
  }
  return <PromotionForm promotion={promotion.data} />
}

function defaultEnd(): Date {
  const end = new Date()
  end.setDate(end.getDate() + 7)
  end.setHours(23, 59, 0, 0)
  return end
}

function PromotionForm({ promotion }: { promotion?: PromotionPublic }) {
  const navigate = useNavigate()
  const categories = useQuery(categoriesListCategoriesOptions())
  const locked = promotion !== undefined && promotion.used
  const [name, setName] = useState(promotion?.name ?? '')
  const [discountKind, setDiscountKind] = useState<DiscountKind>(
    promotion?.discount_kind ?? 'percentage',
  )
  const [value, setValue] = useState(promotion ? String(promotion.value) : '')
  const [targetKind, setTargetKind] = useState<TargetKind>(
    promotion?.target_kind ?? 'categories',
  )
  const initialIds = promotion?.targets.map((target) => target.id) ?? []
  const [ids, setIds] = useState<number[]>(initialIds)
  const [picked, setPicked] = useState<Picked[]>(promotion?.targets ?? [])
  const [startsAt, setStartsAt] = useState(() =>
    toLocalInput(promotion?.starts_at ?? new Date()),
  )
  const [endsAt, setEndsAt] = useState(() =>
    toLocalInput(promotion?.ends_at ?? defaultEnd()),
  )
  const [checked, setChecked] = useState(false)

  const byPicking = targetKind === 'skus' || targetKind === 'products'
  const targetIds = byPicking ? picked.map((item) => item.id) : ids
  const amount = Number(value)
  const errors = {
    name: name.trim() ? undefined : 'Nama promo wajib diisi.',
    value:
      amount > 0 && (discountKind === 'fixed' || amount <= 100)
        ? undefined
        : discountKind === 'percentage'
          ? 'Isi 1 sampai 100.'
          : 'Isi potongan per pcs.',
    targets: targetIds.length ? undefined : 'Pilih untuk apa promo ini.',
    period:
      startsAt && endsAt && startsAt < endsAt
        ? undefined
        : 'Promo harus berakhir setelah dimulai.',
  }

  const onSuccess = (saved: PromotionPublic) => {
    queryClient.invalidateQueries({
      queryKey: promotionsListPromotionsQueryKey(),
    })
    toast.success(`Promo ${saved.name} disimpan.`)
    navigate('/promo')
  }
  const create = useMutation({
    ...promotionsCreatePromotionMutation(),
    onSuccess,
  })
  const update = useMutation({
    ...promotionsUpdatePromotionMutation(),
    onSuccess,
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (Object.values(errors).some(Boolean)) return
    const body = {
      name,
      discount_kind: discountKind,
      value: amount,
      target_kind: targetKind,
      target_ids: targetIds,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
    }
    if (promotion) {
      update.mutate({ path: { promotion_id: promotion.id }, body })
    } else {
      create.mutate({ body })
    }
  }
  const changeTargetKind = (kind: TargetKind) => {
    setTargetKind(kind)
    setIds([])
    setPicked([])
  }
  const error = create.error ?? update.error

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl">
      <BackLink to="/promo" label="Promo" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        {promotion ? promotion.name : 'Buat promo'}
      </h1>
      {locked && (
        <p className="mt-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          Promo ini sudah dipakai di struk, jadi tidak bisa diubah. Akhiri dari
          daftar promo, lalu buat yang baru.
        </p>
      )}

      <fieldset disabled={locked} className="contents">
        <section className="mt-6 grid gap-5 rounded-xl border bg-card p-4">
          <Field
            id="promotion-name"
            label="Nama promo"
            error={checked ? errors.name : undefined}
          >
            <Input
              id="promotion-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={100}
              placeholder="Misalnya: Tahun ajaran baru"
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field id="discount-kind" label="Jenis diskon">
              <Select
                value={discountKind}
                onValueChange={(kind) => setDiscountKind(kind as DiscountKind)}
                disabled={locked}
              >
                <SelectTrigger id="discount-kind" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="percentage">Persen</SelectItem>
                  <SelectItem value="fixed">Potongan rupiah per pcs</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field
              id="discount-value"
              label={discountKind === 'percentage' ? 'Diskon (%)' : 'Potongan'}
              error={checked ? errors.value : undefined}
            >
              {discountKind === 'percentage' ? (
                <Input
                  id="discount-value"
                  value={value}
                  onChange={(event) =>
                    setValue(event.target.value.replace(/\D/g, ''))
                  }
                  inputMode="numeric"
                  className="text-right tabular-nums"
                />
              ) : (
                <MoneyInput
                  id="discount-value"
                  value={value}
                  onValueChange={setValue}
                />
              )}
            </Field>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field id="starts-at" label="Mulai">
              <Input
                id="starts-at"
                type="datetime-local"
                value={startsAt}
                onChange={(event) => setStartsAt(event.target.value)}
              />
            </Field>
            <Field
              id="ends-at"
              label="Berakhir"
              error={checked ? errors.period : undefined}
            >
              <Input
                id="ends-at"
                type="datetime-local"
                value={endsAt}
                onChange={(event) => setEndsAt(event.target.value)}
              />
            </Field>
          </div>
        </section>

        <section className="mt-4 grid gap-4 rounded-xl border bg-card p-4">
          <Field
            id="target-kind"
            label="Berlaku untuk"
            error={checked ? errors.targets : undefined}
          >
            <Select
              value={targetKind}
              onValueChange={(kind) => changeTargetKind(kind as TargetKind)}
              disabled={locked}
            >
              <SelectTrigger id="target-kind" className="w-full sm:w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(TARGET_KIND_LABELS) as TargetKind[]).map(
                  (kind) => (
                    <SelectItem key={kind} value={kind}>
                      {TARGET_KIND_LABELS[kind]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </Field>
          {targetKind === 'categories' && (
            <CategoryChecks
              categories={categories.data ?? []}
              selected={ids}
              onToggle={(id) => setIds((current) => toggle(current, id))}
            />
          )}
          {targetKind === 'sub_categories' && (
            <SubCategoryChecks
              categories={categories.data ?? []}
              selected={ids}
              onToggle={(id) => setIds((current) => toggle(current, id))}
            />
          )}
          {byPicking && (
            <div>
              {!locked && (
                <SkuFinder
                  onPick={(option) => {
                    const item =
                      targetKind === 'skus'
                        ? { id: option.id, label: skuName(option) }
                        : { id: option.product_id, label: option.product_name }
                    setPicked((current) =>
                      current.some((other) => other.id === item.id)
                        ? current
                        : [...current, item],
                    )
                  }}
                />
              )}
              {targetKind === 'products' && !locked && (
                <p className="mt-2 text-sm text-muted-foreground">
                  Scan atau cari salah satu SKU; promo berlaku untuk semua
                  ukuran dan warna produknya.
                </p>
              )}
              <Chips
                items={picked}
                onRemove={(id) =>
                  setPicked((current) =>
                    current.filter((item) => item.id !== id),
                  )
                }
              />
            </div>
          )}
        </section>
      </fieldset>

      {error && (
        <p role="alert" className="mt-4 text-destructive">
          {errorMessage(error)}
        </p>
      )}
      {!locked && (
        <Button
          type="submit"
          className="mt-6"
          disabled={create.isPending || update.isPending}
        >
          {create.isPending || update.isPending ? 'Menyimpan…' : 'Simpan'}
        </Button>
      )}
    </form>
  )
}
