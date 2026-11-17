import { useQuery } from '@tanstack/react-query'
import { PrinterIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'react-router'

import {
  goodsReceiptsReadReceipt,
  productionReceiptsReadReceipt,
  productsListSkus,
} from '@/client'
import type { SkuOption } from '@/client'
import { Field } from '@/components/FormDialog'
import { SkuFinder } from '@/components/SkuFinder'
import { Button } from '@/components/ui/button'
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
import { errorMessage } from '@/lib/api'
import { rupiah, variantLabel } from '@/lib/format'

import { Barcode } from './Barcode'

const SIZES = {
  '50x30': { width: 50, height: 30, label: '50 × 30 mm' },
  '40x25': { width: 40, height: 25, label: '40 × 25 mm' },
  '58x40': { width: 58, height: 40, label: '58 × 40 mm' },
} as const
type Size = keyof typeof SIZES

const MAX_COPIES = 500

type Item = { sku: SkuOption; copies: number }

/** What to print, from the address: ?sku=1,2  ?barang-masuk=7  ?hasil-produksi=3 */
async function loadItems(params: URLSearchParams): Promise<Item[]> {
  let wanted: { skuId: number; copies: number }[] = []
  const fromReceipt = params.get('barang-masuk')
  const fromProduction = params.get('hasil-produksi')
  if (fromReceipt || fromProduction) {
    const { data } = fromReceipt
      ? await goodsReceiptsReadReceipt({
          path: { receipt_id: Number(fromReceipt) },
          throwOnError: true,
        })
      : await productionReceiptsReadReceipt({
          path: { receipt_id: Number(fromProduction) },
          throwOnError: true,
        })
    // One label per unit received.
    wanted = data.lines.map((line) => ({
      skuId: line.sku_id,
      copies: Math.min(Math.ceil(Number(line.quantity)), MAX_COPIES),
    }))
  } else {
    wanted = (params.get('sku') ?? '')
      .split(',')
      .map(Number)
      .filter((id) => id > 0)
      .map((skuId) => ({ skuId, copies: 1 }))
  }
  if (wanted.length === 0) return []
  const { data: skus } = await productsListSkus({
    query: { ids: wanted.map((item) => item.skuId) },
    throwOnError: true,
  })
  const byId = new Map(skus.map((sku) => [sku.id, sku]))
  return wanted.flatMap(({ skuId, copies }) => {
    const sku = byId.get(skuId)
    return sku ? [{ sku, copies }] : []
  })
}

export function LabelsPage() {
  const [params] = useSearchParams()
  const initial = useQuery({
    queryKey: ['labels', params.toString()],
    queryFn: () => loadItems(params),
    staleTime: Infinity,
  })

  if (initial.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (initial.isError) {
    return <p className="text-destructive">{errorMessage(initial.error)}</p>
  }
  return <LabelSheet key={params.toString()} initial={initial.data} />
}

function LabelSheet({ initial }: { initial: Item[] }) {
  const [items, setItems] = useState<Item[]>(initial)
  const [size, setSize] = useState<Size>('50x30')
  const [showPrice, setShowPrice] = useState(true)
  const total = items.reduce((sum, item) => sum + item.copies, 0)

  const add = (sku: SkuOption) =>
    setItems((current) =>
      current.some((item) => item.sku.id === sku.id)
        ? current.map((item) =>
            item.sku.id === sku.id
              ? { ...item, copies: Math.min(item.copies + 1, MAX_COPIES) }
              : item,
          )
        : [...current, { sku, copies: 1 }],
    )
  const setCopies = (skuId: number, text: string) =>
    setItems((current) =>
      current.map((item) =>
        item.sku.id === skuId
          ? {
              ...item,
              copies: Math.min(
                Math.max(Number(text.replace(/\D/g, '')) || 0, 0),
                MAX_COPIES,
              ),
            }
          : item,
      ),
    )
  const labels = items.flatMap((item) =>
    Array.from({ length: item.copies }, (_, copy) => ({
      key: `${item.sku.id}-${copy}`,
      sku: item.sku,
    })),
  )
  const { width, height } = SIZES[size]

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cetak Label</h1>
          <p className="mt-1 text-muted-foreground">
            Label barcode untuk barang tanpa barcode pabrik, atau untuk
            mengganti label yang rusak.
          </p>
        </div>
        <Button onClick={() => window.print()} disabled={total === 0}>
          <PrinterIcon />
          Cetak {total} label
        </Button>
      </div>

      <section className="mt-6 flex flex-wrap items-end gap-4 rounded-xl border bg-card p-4">
        <Field id="label-size" label="Ukuran label">
          <Select
            value={size}
            onValueChange={(value) => setSize(value as Size)}
          >
            <SelectTrigger id="label-size" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(SIZES) as Size[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {SIZES[key].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <span className="flex items-center gap-2 pb-1.5">
          <Switch
            id="show-price"
            checked={showPrice}
            onCheckedChange={setShowPrice}
          />
          <Label htmlFor="show-price">Tampilkan harga</Label>
        </span>
        <p className="w-full text-sm text-muted-foreground">
          Atur printer label ke ukuran kertas yang sama, tanpa margin.
        </p>
      </section>

      <SkuFinder onPick={add} />

      {items.length === 0 ? (
        <p className="mt-3 rounded-xl border border-dashed p-6 text-muted-foreground">
          Scan barcode atau cari nama barang untuk menambah label.
        </p>
      ) : (
        <ul className="mt-3 rounded-xl border bg-card">
          {items.map(({ sku, copies }) => {
            const name = [sku.product_name, variantLabel(sku)]
              .filter(Boolean)
              .join(' · ')
            return (
              <li
                key={sku.id}
                className="flex flex-wrap items-center gap-3 border-b p-3 last:border-b-0"
              >
                <span className="min-w-48 flex-1">
                  <span className="block font-medium">{name}</span>
                  <span className="block text-sm text-muted-foreground tabular-nums">
                    {sku.barcode} · {rupiah(sku.selling_price)}
                  </span>
                </span>
                <Input
                  value={String(copies)}
                  onChange={(event) => setCopies(sku.id, event.target.value)}
                  inputMode="numeric"
                  aria-label={`Jumlah label ${name}`}
                  className="w-20 text-right tabular-nums"
                />
                <span className="text-sm text-muted-foreground">label</span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Hapus ${name}`}
                  onClick={() =>
                    setItems((current) =>
                      current.filter((item) => item.sku.id !== sku.id),
                    )
                  }
                >
                  <Trash2Icon />
                </Button>
              </li>
            )
          })}
        </ul>
      )}

      {labels.length > 0 && (
        <>
          <h2 className="mt-8 font-semibold">Pratinjau</h2>
          <div className="mt-3 flex flex-wrap gap-3">
            {labels.slice(0, 60).map(({ key, sku }) => (
              <div
                key={key}
                className="rounded-sm bg-white shadow-sm ring-1 ring-border"
              >
                <BarcodeLabel
                  sku={sku}
                  width={width}
                  height={height}
                  showPrice={showPrice}
                />
              </div>
            ))}
          </div>
          {labels.length > 60 && (
            <p className="mt-2 text-sm text-muted-foreground">
              dan {labels.length - 60} label lagi.
            </p>
          )}
        </>
      )}

      {createPortal(
        <div className="print-only">
          <style>{`@page { size: ${width}mm ${height}mm; margin: 0; }`}</style>
          {labels.map(({ key, sku }) => (
            <div key={key} style={{ breakAfter: 'page' }}>
              <BarcodeLabel
                sku={sku}
                width={width}
                height={height}
                showPrice={showPrice}
              />
            </div>
          ))}
        </div>,
        document.body,
      )}
    </>
  )
}

function BarcodeLabel({
  sku,
  width,
  height,
  showPrice,
}: {
  sku: SkuOption
  width: number
  height: number
  showPrice: boolean
}) {
  const variant = variantLabel(sku)
  return (
    <div
      data-label
      className="flex flex-col overflow-hidden px-[1.5mm] py-[1mm] text-black"
      style={{ width: `${width}mm`, height: `${height}mm` }}
    >
      <p className="truncate text-[7pt] leading-tight font-semibold">
        {sku.product_name}
      </p>
      <p className="flex justify-between gap-1 text-[7pt] leading-tight">
        <span className="truncate">{variant}</span>
        {showPrice && (
          <span className="font-semibold whitespace-nowrap">
            {rupiah(sku.selling_price)}
          </span>
        )}
      </p>
      <div className="mt-[0.5mm] min-h-0 flex-1">
        <Barcode value={sku.barcode} />
      </div>
    </div>
  )
}
