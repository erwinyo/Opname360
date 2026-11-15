import { useMutation, useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import {
  supplierReturnsCompleteReturn,
  supplierReturnsCreateReturn,
  supplierReturnsUpdateReturn,
} from '@/client'
import type { GoodsReceiptPublic, SupplierReturnPublic } from '@/client'
import {
  goodsReceiptsListReceiptsOptions,
  goodsReceiptsReadReceiptOptions,
  supplierReturnsDiscardReturnMutation,
  supplierReturnsReadReturnOptions,
  supplierReturnsReverseReturnMutation,
} from '@/client/@tanstack/react-query.gen'
import {
  BackLink,
  Facts,
  ReversalNotice,
  ReverseDialog,
  StatusBadge,
} from '@/components/documents'
import { Field, FormDialog } from '@/components/FormDialog'
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
  money,
  parseQuantity,
  quantity,
  rupiah,
  today,
  variantLabel,
} from '@/lib/format'

const BACK = { to: '/retur-pembelian', label: 'Retur Pembelian' }

export function SupplierReturnPage() {
  const params = useParams()
  const returnId = params.returnId ? Number(params.returnId) : null
  const supplierReturn = useQuery({
    ...supplierReturnsReadReturnOptions({
      path: { return_id: returnId ?? 0 },
    }),
    enabled: returnId !== null,
  })

  if (returnId !== null && supplierReturn.isPending) {
    return <p className="text-muted-foreground">Memuat…</p>
  }
  if (returnId !== null && supplierReturn.isError) {
    return (
      <>
        <BackLink {...BACK} />
        <p className="mt-4 text-destructive">
          {errorMessage(supplierReturn.error)}
        </p>
      </>
    )
  }
  if (supplierReturn.data && supplierReturn.data.status !== 'draft') {
    return <ReturnView supplierReturn={supplierReturn.data} />
  }
  return <NewOrDraft draft={supplierReturn.data} />
}

/** Pick the Goods Receipt first; a draft already has one. */
function NewOrDraft({ draft }: { draft?: SupplierReturnPublic }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const receiptId = draft?.goods_receipt_id ?? Number(searchParams.get('dari'))
  const receipts = useQuery({
    ...goodsReceiptsListReceiptsOptions({
      query: { status: 'completed', limit: 200 },
    }),
    enabled: !draft,
  })
  const receipt = useQuery({
    ...goodsReceiptsReadReceiptOptions({ path: { receipt_id: receiptId } }),
    enabled: receiptId > 0,
  })

  return (
    <>
      <BackLink {...BACK} />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        {draft ? 'Draf retur pembelian' : 'Retur pembelian baru'}
      </h1>

      {!draft && (
        <section className="mt-6 rounded-xl border bg-card p-4">
          <Field
            id="receipt"
            label="Dari barang masuk"
            hint="Retur selalu mengikuti satu barang masuk, supaya harga pengembaliannya sama dengan harga belinya."
          >
            <Select
              value={receiptId > 0 ? String(receiptId) : ''}
              onValueChange={(value) => setSearchParams({ dari: value })}
            >
              <SelectTrigger id="receipt" className="w-full">
                <SelectValue placeholder="Pilih barang masuk" />
              </SelectTrigger>
              <SelectContent>
                {receipts.data?.items.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.number} · {item.supplier_name} ·{' '}
                    {formatDate(item.received_on)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </section>
      )}

      {receipt.isError && (
        <p className="mt-6 text-destructive">{errorMessage(receipt.error)}</p>
      )}
      {receipt.data && (
        <ReturnForm
          key={receipt.data.id}
          receipt={receipt.data}
          draft={draft}
        />
      )}
    </>
  )
}

function ReturnForm({
  receipt,
  draft,
}: {
  receipt: GoodsReceiptPublic
  draft?: SupplierReturnPublic
}) {
  const navigate = useNavigate()
  const [returnedOn, setReturnedOn] = useState(draft?.returned_on ?? today())
  const [note, setNote] = useState(draft?.note ?? '')
  const [amounts, setAmounts] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      draft?.lines.map((line) => [
        line.goods_receipt_line_id,
        String(Number(line.quantity)).replace('.', ','),
      ]) ?? [],
    ),
  )
  const [checked, setChecked] = useState(false)
  const [dialog, setDialog] = useState<'complete' | 'discard' | null>(null)
  const savedId = useRef(draft?.id ?? null)

  const rows = receipt.lines.map((line) => {
    const left = Number(line.quantity) - Number(line.returned_quantity)
    const text = amounts[line.id] ?? ''
    const amount = text.trim() === '' ? 0 : parseQuantity(text)
    const error = Number.isNaN(amount) || amount < 0
      ? 'Isi angka.'
      : amount > left
        ? `Paling banyak ${quantity(left)} ${line.stock_unit}.`
        : undefined
    return { line, left, text, amount, error }
  })
  const chosen = rows.filter((row) => row.amount > 0 && !row.error)
  const invalid = rows.some((row) => row.error) || !returnedOn
  const total = chosen.reduce(
    (sum, row) => sum + row.amount * Number(row.line.unit_cost),
    0,
  )
  const receiptReversed = receipt.status !== 'completed'

  const save = async () => {
    const body = {
      goods_receipt_id: receipt.id,
      returned_on: returnedOn,
      note,
      lines: chosen.map((row) => ({
        goods_receipt_line_id: row.line.id,
        quantity: row.amount,
      })),
    }
    const { data } =
      savedId.current === null
        ? await supplierReturnsCreateReturn({ body, throwOnError: true })
        : await supplierReturnsUpdateReturn({
            path: { return_id: savedId.current },
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
      toast.success('Draf retur disimpan.')
      navigate(BACK.to)
    },
  })
  const complete = useMutation({
    mutationFn: async () => {
      const saved = await save()
      const { data } = await supplierReturnsCompleteReturn({
        path: { return_id: saved.id },
        throwOnError: true,
      })
      return data
    },
    onSuccess: (completed) => {
      queryClient.invalidateQueries()
      toast.success(`Retur ${completed.number} selesai. Stok berkurang.`)
      navigate(`/retur-pembelian/${completed.id}`, { replace: true })
    },
    onError: () => setDialog(null),
  })
  const discard = useMutation({
    ...supplierReturnsDiscardReturnMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries()
      toast.success('Draf dibuang.')
      navigate(BACK.to)
    },
  })
  const failure = saveDraft.error ?? complete.error

  if (receiptReversed) {
    return (
      <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
        Barang masuk {receipt.number} sudah dibatalkan, jadi barangnya tidak
        bisa diretur.
      </p>
    )
  }

  return (
    <>
      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          setChecked(true)
          if (!invalid && chosen.length > 0) saveDraft.mutate()
        }}
        noValidate
      >
        <section className="mt-4 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-3">
          <Field id="supplier" label="Pemasok">
            <p id="supplier" className="py-1.5 font-medium">
              {receipt.supplier_name}
            </p>
          </Field>
          <Field id="returned-on" label="Tanggal retur">
            <Input
              id="returned-on"
              type="date"
              value={returnedOn}
              onChange={(event) => setReturnedOn(event.target.value)}
            />
          </Field>
          <Field id="note" label="Alasan atau catatan">
            <Input
              id="note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="mis. jahitan rusak"
            />
          </Field>
        </section>

        <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Barang</TableHead>
                <TableHead className="text-right">Diterima</TableHead>
                <TableHead className="text-right">Bisa diretur</TableHead>
                <TableHead className="text-right">Harga beli</TableHead>
                <TableHead className="w-32 text-right">Jumlah retur</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ line, left, text, error }) => {
                const name = [line.product_name, variantLabel(line)]
                  .filter(Boolean)
                  .join(' · ')
                return (
                  <TableRow key={line.id}>
                    <TableCell>
                      <span className="font-medium">{name}</span>
                      <span className="block text-sm text-muted-foreground tabular-nums">
                        {line.code} · {line.barcode}
                      </span>
                      {error && (
                        <span className="block text-sm text-destructive">
                          {error}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {quantity(line.quantity)} {line.stock_unit}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {quantity(left)} {line.stock_unit}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(line.unit_cost)}
                    </TableCell>
                    <TableCell>
                      <Input
                        value={text}
                        onChange={(event) =>
                          setAmounts((current) => ({
                            ...current,
                            [line.id]: event.target.value,
                          }))
                        }
                        inputMode="decimal"
                        placeholder="0"
                        disabled={left <= 0}
                        aria-label={`Jumlah retur ${name}`}
                        aria-invalid={Boolean(error)}
                        className="text-right tabular-nums"
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell colSpan={4} className="text-right">
                  Nilai retur
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {rupiah(Math.round(total))}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>

        {failure != null && (
          <p role="alert" className="mt-6 text-sm text-destructive">
            {errorMessage(failure)}
          </p>
        )}
        {checked && !invalid && chosen.length === 0 && (
          <p role="alert" className="mt-6 text-sm text-destructive">
            Isi jumlah retur untuk minimal satu barang.
          </p>
        )}

        <div className="mt-6 flex flex-wrap gap-2 border-t pt-4">
          <Button
            type="button"
            disabled={complete.isPending}
            onClick={() => {
              setChecked(true)
              if (!invalid && chosen.length > 0) setDialog('complete')
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
          {draft && (
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
          title="Selesaikan retur?"
          description={`${chosen.length} barang keluar dari stok. ${receipt.supplier_name} berutang pengembalian ${rupiah(Math.round(total))}. Setelah diselesaikan, dokumen ini tidak bisa diubah lagi.`}
          submitLabel="Selesaikan"
          pending={complete.isPending}
          error={null}
          onSubmit={() => complete.mutate()}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'discard' && draft && (
        <FormDialog
          title="Buang draf ini?"
          description="Draf dihapus. Stok tidak berubah."
          submitLabel="Buang draf"
          destructive
          pending={discard.isPending}
          error={discard.error}
          onSubmit={() => discard.mutate({ path: { return_id: draft.id } })}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

function ReturnView({
  supplierReturn,
}: {
  supplierReturn: SupplierReturnPublic
}) {
  const [reversing, setReversing] = useState(false)
  const reverse = useMutation({
    ...supplierReturnsReverseReturnMutation(),
    onSuccess: (reversed) => {
      queryClient.invalidateQueries()
      toast.success(`Retur ${reversed.number} dibatalkan. Barang kembali ke stok.`)
      setReversing(false)
    },
  })

  return (
    <>
      <BackLink {...BACK} />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight tabular-nums">
          {supplierReturn.number}
        </h1>
        <StatusBadge status={supplierReturn.status} />
        {supplierReturn.status === 'completed' && (
          <Button
            variant="ghost"
            className="ml-auto text-destructive hover:text-destructive"
            onClick={() => setReversing(true)}
          >
            Batalkan
          </Button>
        )}
      </div>

      {supplierReturn.reversal && (
        <ReversalNotice reversal={supplierReturn.reversal} />
      )}

      <Facts
        facts={[
          ['Pemasok', supplierReturn.supplier_name],
          [
            'Dari barang masuk',
            <Link
              key="receipt"
              to={`/barang-masuk/${supplierReturn.goods_receipt_id}`}
              className="text-primary tabular-nums underline-offset-4 hover:underline"
            >
              {supplierReturn.goods_receipt_number}
            </Link>,
          ],
          ['Tanggal retur', formatDate(supplierReturn.returned_on)],
          ['Lokasi', supplierReturn.location_name],
          [
            'Diselesaikan',
            supplierReturn.completed_at
              ? `${supplierReturn.completed_by_name ?? '–'} · ${formatDateTime(supplierReturn.completed_at)}`
              : '–',
          ],
        ]}
        note={supplierReturn.note}
      />

      <div className="mt-6 overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Barang</TableHead>
              <TableHead className="text-right">Jumlah</TableHead>
              <TableHead className="text-right">Harga beli</TableHead>
              <TableHead className="text-right">Nilai retur</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {supplierReturn.lines.map((line) => (
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
                  {money(line.total_refund)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3} className="text-right">
                Total
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {money(supplierReturn.total_refund)}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>

      {reversing && (
        <ReverseDialog
          title={`Batalkan ${supplierReturn.number}?`}
          description="Barang di retur ini masuk lagi ke stok dengan harga pokok yang sama seperti saat keluar."
          pending={reverse.isPending}
          error={reverse.error}
          onReverse={(reason) =>
            reverse.mutate({
              path: { return_id: supplierReturn.id },
              body: { reason },
            })
          }
          onClose={() => setReversing(false)}
        />
      )}
    </>
  )
}
