import { useMutation, useQuery } from '@tanstack/react-query'
import { Trash2Icon } from 'lucide-react'
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import {
  productionReceiptsCompleteReceipt,
  productionReceiptsCreateReceipt,
  productionReceiptsUpdateReceipt,
} from '@/client'
import type { ProductionReceiptPublic, SkuOption } from '@/client'
import {
  productionReceiptsDiscardReceiptMutation,
  productionReceiptsReadReceiptOptions,
  productionReceiptsReverseReceiptMutation,
} from '@/client/@tanstack/react-query.gen'
import {
  BackLink,
  Facts,
  ReversalNotice,
  ReverseDialog,
  StatusBadge,
} from '@/components/documents'
import { Field, FormDialog } from '@/components/FormDialog'
import { SkuFinder } from '@/components/SkuFinder'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage, queryClient } from '@/lib/api'
import {
  formatDate,
  formatDateTime,
  groupDigits,
  money,
  onlyDigits,
  parseQuantity,
  quantity,
  rupiah,
  today,
  variantLabel,
} from '@/lib/format'

const BACK = { to: '/hasil-produksi', label: 'Hasil Produksi' }

export function ProductionReceiptPage() {
  const params = useParams()
  const receiptId = params.receiptId ? Number(params.receiptId) : null
  const receipt = useQuery({
    ...productionReceiptsReadReceiptOptions({
      path: { receipt_id: receiptId ?? 0 },
    }),
    enabled: receiptId !== null,
  })

  if (receiptId !== null && receipt.isPending) {
    return <p className="text-muted-foreground">Memuat…</p>
  }
  if (receiptId !== null && receipt.isError) {
    return (
      <>
        <BackLink {...BACK} />
        <p className="mt-4 text-destructive">{errorMessage(receipt.error)}</p>
      </>
    )
  }
  if (receipt.data && receipt.data.status !== 'draft') {
    return <ProductionView receipt={receipt.data} />
  }
  return <ProductionForm key={receiptId ?? 'new'} receipt={receipt.data} />
}

type Line = {
  key: number
  skuId: number
  name: string
  detail: string
  unit: string
  quantity: string
  cost: string
}

let nextKey = 1

const lineTotal = (line: Line) =>
  (parseQuantity(line.quantity) || 0) * Number(line.cost || 0)

function ProductionForm({ receipt }: { receipt?: ProductionReceiptPublic }) {
  const navigate = useNavigate()
  const [producedOn, setProducedOn] = useState(receipt?.produced_on ?? today())
  const [note, setNote] = useState(receipt?.note ?? '')
  const [lines, setLines] = useState<Line[]>(
    receipt?.lines.map((saved) => ({
      key: nextKey++,
      skuId: saved.sku_id,
      name: [saved.product_name, variantLabel(saved)]
        .filter(Boolean)
        .join(' · '),
      detail: `${saved.code} · ${saved.barcode}`,
      unit: saved.stock_unit,
      quantity: String(Number(saved.quantity)).replace('.', ','),
      cost: String(Math.round(Number(saved.unit_cost))),
    })) ?? [],
  )
  const [checked, setChecked] = useState(false)
  const [dialog, setDialog] = useState<'complete' | 'discard' | null>(null)
  const savedId = useRef(receipt?.id ?? null)

  const lineErrors = lines.map((line) =>
    !(parseQuantity(line.quantity) > 0)
      ? 'Jumlah harus lebih dari 0.'
      : line.cost === ''
        ? 'Biaya per satuan wajib diisi.'
        : undefined,
  )
  const dateError = producedOn ? undefined : 'Tanggal wajib diisi.'
  const invalid = Boolean(dateError) || lineErrors.some(Boolean)
  const total = lines.reduce((sum, line) => sum + lineTotal(line), 0)

  const save = async () => {
    const body = {
      produced_on: producedOn,
      note,
      lines: lines.map((line) => ({
        sku_id: line.skuId,
        quantity: parseQuantity(line.quantity),
        unit_cost: Number(line.cost),
      })),
    }
    const { data } =
      savedId.current === null
        ? await productionReceiptsCreateReceipt({ body, throwOnError: true })
        : await productionReceiptsUpdateReceipt({
            path: { receipt_id: savedId.current },
            body,
            throwOnError: true,
          })
    savedId.current = data.id
    return data
  }
  const saveDraft = useMutation({
    mutationFn: save,
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Draf hasil produksi disimpan.')
      navigate(BACK.to)
    },
  })
  const complete = useMutation({
    mutationFn: async () => {
      const saved = await save()
      const { data } = await productionReceiptsCompleteReceipt({
        path: { receipt_id: saved.id },
        throwOnError: true,
      })
      return data
    },
    onSuccess: (completed) => {
      queryClient.invalidateQueries()
      toast.success(
        `Hasil produksi ${completed.number} selesai. Stok bertambah.`,
      )
      navigate(`/hasil-produksi/${completed.id}`, { replace: true })
    },
    onError: () => setDialog(null),
  })
  const discard = useMutation({
    ...productionReceiptsDiscardReceiptMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Draf dibuang.')
      navigate(BACK.to)
    },
  })

  const addSku = (option: SkuOption) =>
    setLines((current) => {
      const existing = current.find((line) => line.skuId === option.id)
      if (existing) {
        return current.map((line) =>
          line === existing
            ? {
                ...line,
                quantity: String((parseQuantity(line.quantity) || 0) + 1),
              }
            : line,
        )
      }
      return [
        ...current,
        {
          key: nextKey++,
          skuId: option.id,
          name: [option.product_name, variantLabel(option)]
            .filter(Boolean)
            .join(' · '),
          detail: `${option.code} · ${option.barcode}`,
          unit: option.stock_unit,
          quantity: '1',
          cost: option.latest_unit_cost
            ? String(Math.round(Number(option.latest_unit_cost)))
            : '',
        },
      ]
    })
  const change = (key: number, patch: Partial<Line>) =>
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  const failure = saveDraft.error ?? complete.error

  return (
    <>
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          setChecked(true)
          if (!invalid) saveDraft.mutate()
        }}
        noValidate
      >
        <BackLink {...BACK} />
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">
          {receipt ? 'Draf hasil produksi' : 'Hasil produksi baru'}
        </h1>

        <section className="mt-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-3">
          <Field
            id="produced-on"
            label="Tanggal selesai dibuat"
            error={checked ? dateError : undefined}
          >
            <Input
              id="produced-on"
              type="date"
              value={producedOn}
              onChange={(event) => setProducedOn(event.target.value)}
            />
          </Field>
          <Field
            id="note"
            label="Catatan"
            hint="Misalnya penjahit atau nomor order."
            className="sm:col-span-2"
          >
            <Input
              id="note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
        </section>

        <h2 className="mt-8 font-semibold">Barang jadi</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Biaya per satuan: semua biaya membuat satu barang (kain, ongkos jahit,
          dan lainnya). Itu menjadi harga pokoknya di stok.
        </p>
        <SkuFinder onPick={addSku} />

        {lines.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed p-6 text-muted-foreground">
            Scan barcode atau cari nama barang untuk menambah baris.
          </p>
        ) : (
          <div className="mt-3 rounded-xl border bg-card">
            {lines.map((line, index) => {
              const error = checked ? lineErrors[index] : undefined
              return (
                <div
                  key={line.key}
                  className="flex flex-wrap items-start gap-x-3 gap-y-2 border-b p-3 last:border-b-0"
                >
                  <div className="min-w-48 flex-1">
                    <p className="font-medium">{line.name}</p>
                    <p className="text-sm text-muted-foreground tabular-nums">
                      {line.detail}
                    </p>
                    {error && (
                      <p className="mt-1 text-sm text-destructive">{error}</p>
                    )}
                  </div>
                  <Input
                    value={line.quantity}
                    onChange={(e) =>
                      change(line.key, { quantity: e.target.value })
                    }
                    inputMode="decimal"
                    aria-label={`Jumlah ${line.name}`}
                    className="w-20 text-right tabular-nums"
                  />
                  <span className="w-12 py-1.5 text-sm text-muted-foreground">
                    {line.unit}
                  </span>
                  <div className="relative w-36">
                    <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">
                      Rp
                    </span>
                    <Input
                      value={groupDigits(line.cost)}
                      onChange={(e) =>
                        change(line.key, { cost: onlyDigits(e.target.value) })
                      }
                      inputMode="numeric"
                      aria-label={`Biaya per ${line.unit} ${line.name}`}
                      className="pl-9 text-right tabular-nums"
                    />
                  </div>
                  <span className="w-32 py-1.5 text-right tabular-nums">
                    {rupiah(Math.round(lineTotal(line)))}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Hapus ${line.name}`}
                    onClick={() =>
                      setLines((current) =>
                        current.filter((other) => other.key !== line.key),
                      )
                    }
                  >
                    <Trash2Icon />
                  </Button>
                </div>
              )
            })}
            <div className="flex justify-end gap-6 border-t bg-muted/40 p-3 font-medium">
              <span>Total biaya</span>
              <span className="tabular-nums">{rupiah(Math.round(total))}</span>
            </div>
          </div>
        )}

        {failure != null && (
          <p role="alert" className="mt-6 text-sm text-destructive">
            {errorMessage(failure)}
          </p>
        )}
        {checked && invalid && (
          <p role="alert" className="mt-6 text-sm text-destructive">
            Masih ada isian yang perlu diperbaiki.
          </p>
        )}

        <div className="mt-6 flex flex-wrap gap-2 border-t pt-4">
          <Button
            type="button"
            disabled={complete.isPending}
            onClick={() => {
              setChecked(true)
              if (!invalid && lines.length > 0) setDialog('complete')
            }}
          >
            Selesaikan
          </Button>
          <Button type="submit" variant="outline" disabled={saveDraft.isPending}>
            {saveDraft.isPending ? 'Menyimpan…' : 'Simpan draf'}
          </Button>
          <Button type="button" variant="ghost" asChild>
            <Link to={BACK.to}>Batal</Link>
          </Button>
          {receipt && (
            <Button
              type="button"
              variant="ghost"
              className="ml-auto text-destructive hover:text-destructive"
              onClick={() => setDialog('discard')}
            >
              Buang draf
            </Button>
          )}
        </div>
      </form>

      {dialog === 'complete' && (
        <FormDialog
          title="Selesaikan hasil produksi?"
          description={`Stok ${lines.length} barang bertambah dengan biaya ${rupiah(Math.round(total))}. Setelah diselesaikan, dokumen ini tidak bisa diubah lagi.`}
          submitLabel="Selesaikan"
          pending={complete.isPending}
          error={null}
          onSubmit={() => complete.mutate()}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'discard' && receipt && (
        <FormDialog
          title="Buang draf ini?"
          description="Draf dihapus. Stok tidak berubah."
          submitLabel="Buang draf"
          destructive
          pending={discard.isPending}
          error={discard.error}
          onSubmit={() => discard.mutate({ path: { receipt_id: receipt.id } })}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

function ProductionView({ receipt }: { receipt: ProductionReceiptPublic }) {
  const [reversing, setReversing] = useState(false)
  const reverse = useMutation({
    ...productionReceiptsReverseReceiptMutation(),
    onSuccess: (reversed) => {
      queryClient.invalidateQueries()
      toast.success(`Hasil produksi ${reversed.number} dibatalkan.`)
      setReversing(false)
    },
  })

  return (
    <>
      <BackLink {...BACK} />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight tabular-nums">
          {receipt.number}
        </h1>
        <StatusBadge status={receipt.status} />
        {receipt.status === 'completed' && (
          <Button
            variant="ghost"
            className="ml-auto text-destructive hover:text-destructive"
            onClick={() => setReversing(true)}
          >
            Batalkan
          </Button>
        )}
      </div>

      {receipt.reversal && <ReversalNotice reversal={receipt.reversal} />}

      <Facts
        facts={[
          ['Tanggal selesai dibuat', formatDate(receipt.produced_on)],
          ['Lokasi', receipt.location_name],
          [
            'Diselesaikan',
            receipt.completed_at
              ? `${receipt.completed_by_name ?? '–'} · ${formatDateTime(receipt.completed_at)}`
              : '–',
          ],
        ]}
        note={receipt.note}
      />

      <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Barang</TableHead>
              <TableHead className="text-right">Jumlah</TableHead>
              <TableHead className="text-right">Biaya per satuan</TableHead>
              <TableHead className="text-right">Subtotal</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {receipt.lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>
                  <Link to={`/stok/${line.sku_id}`} className="font-medium">
                    {[line.product_name, variantLabel(line)]
                      .filter(Boolean)
                      .join(' · ')}
                  </Link>
                  <span className="block text-sm text-muted-foreground tabular-nums">
                    {line.code} · {line.barcode}
                  </span>
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {quantity(line.quantity)} {line.stock_unit}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {money(line.unit_cost)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {money(line.total_cost)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3} className="text-right">
                Total biaya
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {money(receipt.total_cost)}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>

      {reversing && (
        <ReverseDialog
          title={`Batalkan ${receipt.number}?`}
          description="Barang jadi di dokumen ini dikeluarkan lagi dari stok dengan biaya yang sama. Barang yang sudah terjual membuat stoknya minus."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({ path: { receipt_id: receipt.id }, body: { reason } })
          }
          onClose={() => setReversing(false)}
        />
      )}
    </>
  )
}
