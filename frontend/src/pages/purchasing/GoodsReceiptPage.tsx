import { useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon, PrinterIcon, Trash2Icon, Undo2Icon } from 'lucide-react'
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import {
  goodsReceiptsCompleteReceipt,
  goodsReceiptsCreateReceipt,
  goodsReceiptsUpdateReceipt,
} from '@/client'
import type {
  GoodsReceiptLinePublic,
  GoodsReceiptPublic,
  PaymentStatus,
  SkuOption,
} from '@/client'
import {
  goodsReceiptsDiscardReceiptMutation,
  goodsReceiptsReadReceiptOptions,
  goodsReceiptsReverseReceiptMutation,
  suppliersListSuppliersOptions,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { PAYMENT_LABELS } from '@/lib/labels'

import { SupplierDialog } from './SuppliersPage'

export function GoodsReceiptPage() {
  const params = useParams()
  const receiptId = params.receiptId ? Number(params.receiptId) : null
  const receipt = useQuery({
    ...goodsReceiptsReadReceiptOptions({
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
        <BackLink to="/barang-masuk" label="Barang Masuk" />
        <p className="mt-4 text-destructive">{errorMessage(receipt.error)}</p>
      </>
    )
  }
  if (receipt.data && receipt.data.status !== 'draft') {
    return <ReceiptView receipt={receipt.data} />
  }
  return <ReceiptForm key={receiptId ?? 'new'} receipt={receipt.data} />
}

/** One line as typed: a quantity and a cost in the unit chosen for it. */
type Line = {
  key: number
  skuId: number
  name: string
  detail: string
  stockUnit: string
  packName: string | null
  packSize: number | null
  inPacks: boolean
  quantity: string
  cost: string
}

let nextKey = 1

function lineFromOption(option: SkuOption): Line {
  return {
    key: nextKey++,
    skuId: option.id,
    name: [option.product_name, variantLabel(option)]
      .filter(Boolean)
      .join(' · '),
    detail: `${option.code} · ${option.barcode}`,
    stockUnit: option.stock_unit,
    packName: option.purchase_pack_name,
    packSize: option.purchase_pack_size
      ? Number(option.purchase_pack_size)
      : null,
    inPacks: false,
    quantity: '1',
    cost: option.latest_unit_cost
      ? String(Math.round(Number(option.latest_unit_cost)))
      : '',
  }
}

function lineFromSaved(saved: GoodsReceiptLinePublic): Line {
  const inPacks = saved.pack_quantity !== null
  return {
    key: nextKey++,
    skuId: saved.sku_id,
    name: [saved.product_name, variantLabel(saved)].filter(Boolean).join(' · '),
    detail: `${saved.code} · ${saved.barcode}`,
    stockUnit: saved.stock_unit,
    packName: saved.purchase_pack_name,
    packSize: saved.purchase_pack_size
      ? Number(saved.purchase_pack_size)
      : null,
    inPacks,
    quantity: String(
      Number(inPacks ? saved.pack_quantity : saved.quantity),
    ).replace('.', ','),
    cost: String(
      Math.round(Number(inPacks ? saved.pack_cost : saved.unit_cost)),
    ),
  }
}

type LineErrors = { quantity?: string; cost?: string }

const lineTotal = (line: Line) =>
  (parseQuantity(line.quantity) || 0) * Number(line.cost || 0)

function ReceiptForm({ receipt }: { receipt?: GoodsReceiptPublic }) {
  const navigate = useNavigate()
  const suppliers = useQuery(suppliersListSuppliersOptions())
  const [supplierId, setSupplierId] = useState(
    receipt ? String(receipt.supplier_id) : '',
  )
  const [receivedOn, setReceivedOn] = useState(receipt?.received_on ?? today())
  const [invoice, setInvoice] = useState(receipt?.supplier_invoice ?? '')
  const [payment, setPayment] = useState<PaymentStatus>(
    receipt?.payment_status ?? 'paid',
  )
  const [note, setNote] = useState(receipt?.note ?? '')
  const [lines, setLines] = useState<Line[]>(
    receipt ? receipt.lines.map(lineFromSaved) : [],
  )
  const [checked, setChecked] = useState(false)
  const [dialog, setDialog] = useState<
    'complete' | 'discard' | 'supplier' | null
  >(null)
  // Once saved, later saves update the same draft even if completing failed.
  const savedId = useRef(receipt?.id ?? null)

  const lineErrors = lines.map((line) => {
    const amount = parseQuantity(line.quantity)
    return {
      quantity: amount > 0 ? undefined : 'Jumlah harus lebih dari 0.',
      cost: line.cost === '' ? 'Harga beli wajib diisi.' : undefined,
    }
  })
  const errors = {
    supplier: supplierId ? undefined : 'Pilih pemasok.',
    receivedOn: receivedOn ? undefined : 'Tanggal terima wajib diisi.',
  }
  const invalid =
    Boolean(errors.supplier || errors.receivedOn) ||
    lineErrors.some((error) => error.quantity || error.cost)
  const total = lines.reduce((sum, line) => sum + lineTotal(line), 0)

  const save = async () => {
    const body = {
      supplier_id: Number(supplierId),
      received_on: receivedOn,
      supplier_invoice: invoice,
      payment_status: payment,
      note,
      lines: lines.map((line) => ({
        sku_id: line.skuId,
        quantity: parseQuantity(line.quantity),
        unit_cost: Number(line.cost),
        in_packs: line.inPacks,
      })),
    }
    const { data } =
      savedId.current === null
        ? await goodsReceiptsCreateReceipt({ body, throwOnError: true })
        : await goodsReceiptsUpdateReceipt({
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
      toast.success('Draf barang masuk disimpan.')
      navigate('/barang-masuk')
    },
  })
  const complete = useMutation({
    mutationFn: async () => {
      const saved = await save()
      const { data } = await goodsReceiptsCompleteReceipt({
        path: { receipt_id: saved.id },
        throwOnError: true,
      })
      return data
    },
    onSuccess: (completed) => {
      queryClient.invalidateQueries()
      toast.success(`Barang masuk ${completed.number} selesai. Stok bertambah.`)
      navigate(`/barang-masuk/${completed.id}`, { replace: true })
    },
    onError: () => setDialog(null),
  })
  const discard = useMutation({
    ...goodsReceiptsDiscardReceiptMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Draf dibuang.')
      navigate('/barang-masuk')
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (!invalid) saveDraft.mutate()
  }
  const askToComplete = () => {
    setChecked(true)
    if (!invalid && lines.length > 0) setDialog('complete')
  }

  const addSku = (option: SkuOption) =>
    setLines((current) => {
      const existing = current.find(
        (line) => line.skuId === option.id && !line.inPacks,
      )
      if (!existing) return [...current, lineFromOption(option)]
      // Scanning the same SKU again counts one more.
      return current.map((line) =>
        line === existing
          ? {
              ...line,
              quantity: String((parseQuantity(line.quantity) || 0) + 1),
            }
          : line,
      )
    })
  const change = (key: number, patch: Partial<Line>) =>
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )

  const activeSuppliers = suppliers.data?.filter(
    (supplier) =>
      supplier.is_active || String(supplier.id) === supplierId,
  )
  const failure = saveDraft.error ?? complete.error

  return (
    <>
      <form onSubmit={submit} noValidate>
        <BackLink to="/barang-masuk" label="Barang Masuk" />
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">
          {receipt ? 'Draf barang masuk' : 'Barang masuk baru'}
        </h1>

        <section className="mt-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field
            id="supplier"
            label="Pemasok"
            error={checked ? errors.supplier : undefined}
            className="sm:col-span-2"
          >
            <div className="flex gap-2">
              <Select value={supplierId} onValueChange={setSupplierId}>
                <SelectTrigger id="supplier" className="w-full">
                  <SelectValue placeholder="Pilih pemasok" />
                </SelectTrigger>
                <SelectContent>
                  {activeSuppliers?.map((supplier) => (
                    <SelectItem key={supplier.id} value={String(supplier.id)}>
                      {supplier.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialog('supplier')}
              >
                <PlusIcon />
                Baru
              </Button>
            </div>
          </Field>
          <Field
            id="received-on"
            label="Tanggal terima"
            error={checked ? errors.receivedOn : undefined}
          >
            <Input
              id="received-on"
              type="date"
              value={receivedOn}
              onChange={(event) => setReceivedOn(event.target.value)}
            />
          </Field>
          <Field id="payment" label="Pembayaran">
            <Select
              value={payment}
              onValueChange={(value) => setPayment(value as PaymentStatus)}
            >
              <SelectTrigger id="payment" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paid">{PAYMENT_LABELS.paid}</SelectItem>
                <SelectItem value="owed">{PAYMENT_LABELS.owed}</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field id="invoice" label="No. faktur pemasok">
            <Input
              id="invoice"
              value={invoice}
              onChange={(event) => setInvoice(event.target.value)}
            />
          </Field>
          <Field id="note" label="Catatan" className="sm:col-span-2 lg:col-span-3">
            <Input
              id="note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </Field>
        </section>

        <h2 className="mt-8 font-semibold">Barang</h2>
        <SkuFinder onPick={addSku} />

        {lines.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed p-6 text-muted-foreground">
            Scan barcode atau cari nama barang untuk menambah baris.
          </p>
        ) : (
          <div className="mt-3 rounded-xl border bg-card">
            {lines.map((line, index) => {
              const error: LineErrors = checked ? lineErrors[index] : {}
              const unit = line.inPacks ? line.packName : line.stockUnit
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
                    {(error.quantity || error.cost) && (
                      <p className="mt-1 text-sm text-destructive">
                        {error.quantity ?? error.cost}
                      </p>
                    )}
                  </div>
                  <Input
                    value={line.quantity}
                    onChange={(e) =>
                      change(line.key, { quantity: e.target.value })
                    }
                    inputMode="decimal"
                    aria-label={`Jumlah ${line.name}`}
                    aria-invalid={Boolean(error.quantity)}
                    className="w-20 text-right tabular-nums"
                  />
                  {line.packName ? (
                    <Select
                      value={line.inPacks ? 'pack' : 'unit'}
                      onValueChange={(value) =>
                        change(line.key, { inPacks: value === 'pack' })
                      }
                    >
                      <SelectTrigger
                        className="w-36"
                        aria-label={`Satuan ${line.name}`}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="unit">{line.stockUnit}</SelectItem>
                        <SelectItem value="pack">
                          {line.packName} ({line.packSize} {line.stockUnit})
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="w-36 py-1.5 text-sm text-muted-foreground">
                      {line.stockUnit}
                    </span>
                  )}
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
                      aria-label={`Harga beli per ${unit} ${line.name}`}
                      aria-invalid={Boolean(error.cost)}
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
              <span>Total</span>
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
        {checked && !invalid && lines.length === 0 && (
          <p className="mt-6 text-sm text-muted-foreground">
            Tambahkan barang dulu sebelum menyelesaikan.
          </p>
        )}

        <div className="mt-6 flex flex-wrap gap-2 border-t pt-4">
          <Button
            type="button"
            onClick={askToComplete}
            disabled={complete.isPending}
          >
            Selesaikan
          </Button>
          <Button type="submit" variant="outline" disabled={saveDraft.isPending}>
            {saveDraft.isPending ? 'Menyimpan…' : 'Simpan draf'}
          </Button>
          <Button type="button" variant="ghost" asChild>
            <Link to="/barang-masuk">Batal</Link>
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

      {/* Outside the form: a dialog's own submit would bubble into it. */}
      {dialog === 'complete' && (
        <FormDialog
          title="Selesaikan barang masuk?"
          description={`Stok ${lines.length} barang akan bertambah senilai ${rupiah(Math.round(total))}. Setelah diselesaikan, dokumen ini tidak bisa diubah lagi.`}
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
      {dialog === 'supplier' && (
        <SupplierDialog
          onClose={() => setDialog(null)}
          onSaved={(supplier) => setSupplierId(String(supplier.id))}
        />
      )}
    </>
  )
}

function ReceiptView({ receipt }: { receipt: GoodsReceiptPublic }) {
  const [reversing, setReversing] = useState(false)
  const reverse = useMutation({
    ...goodsReceiptsReverseReceiptMutation(),
    onSuccess: (reversed) => {
      queryClient.invalidateQueries()
      toast.success(
        `Barang masuk ${reversed.number} dibatalkan. Stok dikurangi kembali.`,
      )
      setReversing(false)
    },
  })
  const returnable = receipt.lines.some(
    (line) => Number(line.quantity) > Number(line.returned_quantity),
  )
  const anyReturned = receipt.lines.some(
    (line) => Number(line.returned_quantity) > 0,
  )

  return (
    <>
      <BackLink to="/barang-masuk" label="Barang Masuk" />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight tabular-nums">
          {receipt.number}
        </h1>
        <StatusBadge status={receipt.status} />
        {receipt.status === 'completed' && (
          <span className="ml-auto flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link to={`/label?barang-masuk=${receipt.id}`}>
                <PrinterIcon />
                Cetak label
              </Link>
            </Button>
            {returnable && (
              <Button variant="outline" asChild>
                <Link to={`/retur-pembelian/baru?dari=${receipt.id}`}>
                  <Undo2Icon />
                  Retur ke pemasok
                </Link>
              </Button>
            )}
            <Button
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={() => setReversing(true)}
            >
              Batalkan
            </Button>
          </span>
        )}
      </div>

      {receipt.reversal && <ReversalNotice reversal={receipt.reversal} />}

      <Facts
        facts={[
          ['Pemasok', receipt.supplier_name],
          ['Tanggal terima', formatDate(receipt.received_on)],
          ['Pembayaran', PAYMENT_LABELS[receipt.payment_status]],
          ['No. faktur pemasok', receipt.supplier_invoice ?? '–'],
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
              {anyReturned && (
                <TableHead className="text-right">Diretur</TableHead>
              )}
              <TableHead className="text-right">Harga beli</TableHead>
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
                  {line.pack_quantity !== null && (
                    <span className="block text-sm text-muted-foreground">
                      {quantity(line.pack_quantity)} {line.pack_name} ×{' '}
                      {quantity(line.pack_size ?? 0)}
                    </span>
                  )}
                </TableCell>
                {anyReturned && (
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {Number(line.returned_quantity) > 0
                      ? `${quantity(line.returned_quantity)} ${line.stock_unit}`
                      : '–'}
                  </TableCell>
                )}
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {money(line.unit_cost)}
                  {line.pack_cost !== null && (
                    <span className="block text-sm text-muted-foreground">
                      {money(line.pack_cost)} / {line.pack_name}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {money(line.total_cost)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={anyReturned ? 4 : 3} className="text-right">
                Total
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
          description="Semua barang di dokumen ini dikeluarkan lagi dari stok dengan harga pokok yang sama. Barang yang sudah terjual membuat stoknya minus."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({
              path: { receipt_id: receipt.id },
              body: { reason },
            })
          }
          onClose={() => setReversing(false)}
        />
      )}
    </>
  )
}
