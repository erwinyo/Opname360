import { useMutation, useQuery } from '@tanstack/react-query'
import {
  CameraIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  ScanBarcodeIcon,
  SearchIcon,
  Undo2Icon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useParams } from 'react-router'

import type { CountCreate, CountSkuOption } from '@/client'
import {
  countingAddCountMutation,
  countingCancelCountMutation,
  countingFindSkusOptions,
  countingReadSheetOptions,
  countingReadSheetQueryKey,
} from '@/client/@tanstack/react-query.gen'
import { CameraScanner } from '@/components/CameraScanner'
import { BackLink } from '@/components/documents'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage, queryClient } from '@/lib/api'
import { cameraScanning } from '@/lib/camera'
import {
  formatDate,
  parseQuantity,
  quantity,
  skuName,
  today,
} from '@/lib/format'
import { cn } from '@/lib/utils'

type Feedback = { ok: boolean; text: string }
type Target = { code: string } | { sku_id: number }
/** A medicine waiting for the Checker to say which Batch it is. */
type Picking = { option: CountSkuOption; target: Target }

const timeOnly = new Intl.DateTimeFormat('id-ID', { timeStyle: 'short' })

/** The Checker's phone: scan or type, see only what you counted yourself. */
export function CountPage() {
  const opnameId = Number(useParams().opnameId)
  const path = { opname_id: opnameId }
  const sheet = useQuery(countingReadSheetOptions({ path }))
  const [code, setCode] = useState('')
  const [amount, setAmount] = useState('1')
  const [camera, setCamera] = useState(false)
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [picking, setPicking] = useState<Picking | null>(null)
  const [newNumber, setNewNumber] = useState('')
  const [newExpiry, setNewExpiry] = useState('')
  const scanInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const timer = setTimeout(() => setSearch(typed.trim()), 300)
    return () => clearTimeout(timer)
  }, [typed])
  const found = useQuery({
    ...countingFindSkusOptions({ path, query: { search } }),
    enabled: search !== '',
  })

  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: countingReadSheetQueryKey({ path }),
    })
  const add = useMutation({
    ...countingAddCountMutation(),
    onSuccess: (entry) => {
      const batch = entry.batch_number ? ` (batch ${entry.batch_number})` : ''
      setFeedback({
        ok: true,
        text: `${skuName(entry)}${batch}: +${quantity(entry.quantity)} ${entry.stock_unit}`,
      })
      setAmount('1')
      setPicking(null)
      void refresh()
    },
    onError: (error) => setFeedback({ ok: false, text: errorMessage(error) }),
  })
  const undo = useMutation({
    ...countingCancelCountMutation(),
    onSuccess: () => {
      setFeedback({ ok: true, text: 'Hitungan dibatalkan.' })
      void refresh()
    },
    onError: (error) => setFeedback({ ok: false, text: errorMessage(error) }),
  })

  const perScan = parseQuantity(amount)
  const amountError =
    Number.isFinite(perScan) && perScan > 0 ? undefined : 'Isi jumlah > 0.'
  const send = (body: Omit<CountCreate, 'quantity'>) => {
    if (amountError) {
      setFeedback({ ok: false, text: amountError })
      return
    }
    add.mutate({ path, body: { ...body, quantity: perScan } })
  }
  const startPicking = (next: Picking) => {
    setPicking(next)
    setNewNumber('')
    setNewExpiry('')
    setFeedback(null)
  }
  /** A medicine first asks for its Batch; anything else is counted. */
  const scan = (scanned: string) => {
    const medicine = sheet.data?.batch_skus.find(
      (option) =>
        option.barcode === scanned ||
        option.code.toLowerCase() === scanned.toLowerCase(),
    )
    if (medicine) startPicking({ option: medicine, target: { code: scanned } })
    else send({ code: scanned })
  }
  const submitCode = (event: FormEvent) => {
    event.preventDefault()
    if (!code.trim()) return
    scan(code.trim())
    setCode('')
    scanInput.current?.focus()
  }
  const submitNewBatch = (event: FormEvent) => {
    event.preventDefault()
    if (!picking || !newNumber.trim() || !newExpiry) return
    send({
      ...picking.target,
      batch_number: newNumber.trim(),
      expires_on: newExpiry,
    })
  }

  if (sheet.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (sheet.isError) {
    return (
      <div className="mx-auto max-w-md">
        <BackLink to="/hitung" label="Hitung Stok" />
        <p className="mt-4 text-destructive">{errorMessage(sheet.error)}</p>
      </div>
    )
  }
  const data = sheet.data

  return (
    <div className="mx-auto max-w-md">
      <BackLink to="/hitung" label="Hitung Stok" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">
        {data.number}
      </h1>
      <p className="mt-1 text-muted-foreground">
        {data.scope_label} · {data.location_name}
      </p>

      {!data.can_count ? (
        <p className="mt-6 rounded-xl border border-dashed p-6 text-muted-foreground">
          Penghitungan sudah ditutup. Terima kasih!
        </p>
      ) : (
        <section className="mt-6 grid gap-4 rounded-xl border bg-card p-4">
          <form onSubmit={submitCode} className="flex items-end gap-2">
            <div className="grid w-20 gap-2">
              <Label htmlFor="amount">Jumlah</Label>
              <Input
                id="amount"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                onFocus={(event) => event.target.select()}
                inputMode="decimal"
                className="text-center tabular-nums"
              />
            </div>
            <div className="grid flex-1 gap-2">
              <Label htmlFor="code">Barcode</Label>
              <div className="relative">
                <ScanBarcodeIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="code"
                  ref={scanInput}
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="Scan atau ketik"
                  autoFocus
                  autoComplete="off"
                  className="pl-8"
                />
              </div>
            </div>
            <Button type="submit" disabled={!code.trim()}>
              Hitung
            </Button>
          </form>
          <p className="-mt-2 text-sm text-muted-foreground">
            Satu scan menambah jumlah ini; sesudahnya kembali ke 1.
          </p>

          {cameraScanning && (
            <div>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCamera((on) => !on)}
              >
                <CameraIcon />
                {camera ? 'Tutup kamera' : 'Scan pakai kamera'}
              </Button>
              {camera && (
                <div className="mt-3">
                  <CameraScanner onScan={scan} />
                </div>
              )}
            </div>
          )}

          {picking && (
            <div className="grid gap-3 rounded-lg border border-primary/40 bg-primary/5 p-3">
              <p className="font-medium">
                Batch yang mana?
                <span className="block text-sm font-normal text-muted-foreground">
                  {skuName(picking.option)} · {amount}{' '}
                  {picking.option.stock_unit}
                </span>
              </p>
              {picking.option.batches && picking.option.batches.length > 0 && (
                <ul className="grid gap-2">
                  {picking.option.batches.map((batch) => {
                    const expired = batch.expires_on < today()
                    return (
                      <li key={batch.id}>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-auto w-full justify-between py-2.5"
                          disabled={add.isPending}
                          onClick={() =>
                            send({ ...picking.target, batch_id: batch.id })
                          }
                        >
                          <span className="font-semibold tabular-nums">
                            {batch.number}
                          </span>
                          <span
                            className={cn(
                              'text-sm tabular-nums',
                              expired
                                ? 'text-destructive'
                                : 'text-muted-foreground',
                            )}
                          >
                            {expired ? 'Kedaluwarsa' : 'Sampai'}{' '}
                            {formatDate(batch.expires_on)}
                          </span>
                        </Button>
                      </li>
                    )
                  })}
                </ul>
              )}
              <form onSubmit={submitNewBatch} className="grid gap-2">
                <Label htmlFor="new-batch">
                  {picking.option.batches?.length
                    ? 'Batch lain'
                    : 'Nomor batch di kemasan'}
                </Label>
                <div className="flex flex-wrap gap-2">
                  <Input
                    id="new-batch"
                    value={newNumber}
                    onChange={(event) => setNewNumber(event.target.value)}
                    placeholder="No. batch"
                    maxLength={50}
                    autoComplete="off"
                    className="w-32 flex-1 uppercase"
                  />
                  <Input
                    type="date"
                    value={newExpiry}
                    onChange={(event) => setNewExpiry(event.target.value)}
                    aria-label="Tanggal kedaluwarsa"
                    className="w-40 flex-1"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    disabled={!newNumber.trim() || !newExpiry || add.isPending}
                  >
                    Hitung batch ini
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setPicking(null)}
                  >
                    Batal
                  </Button>
                </div>
              </form>
            </div>
          )}

          <div
            role="status"
            className={cn(
              'flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium',
              feedback?.ok && 'bg-primary/10 text-primary',
              feedback && !feedback.ok && 'bg-destructive/10 text-destructive',
            )}
          >
            {feedback &&
              (feedback.ok ? (
                <CheckCircle2Icon className="size-4 shrink-0" />
              ) : (
                <CircleAlertIcon className="size-4 shrink-0" />
              ))}
            {feedback?.text}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="by-name">Barang tanpa barcode</Label>
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="by-name"
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                placeholder="Cari nama barang"
                autoComplete="off"
                className="pl-8"
              />
            </div>
            {found.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Tidak ada barang yang cocok dalam opname ini.
              </p>
            )}
            {found.data && found.data.length > 0 && (
              <ul className="rounded-lg border">
                {found.data.map((option) => (
                  <li key={option.id} className="border-b last:border-b-0">
                    <button
                      type="button"
                      onClick={() => {
                        if (option.batches) {
                          startPicking({
                            option,
                            target: { sku_id: option.id },
                          })
                        } else {
                          send({ sku_id: option.id })
                        }
                        setTyped('')
                      }}
                      className="flex w-full items-baseline gap-3 px-3 py-2.5 text-left hover:bg-muted"
                    >
                      <span className="font-medium">{skuName(option)}</span>
                      <span className="ml-auto text-sm text-muted-foreground tabular-nums">
                        {option.code}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      <h2 className="mt-8 font-medium">Hitungan Anda</h2>
      <p className="text-sm text-muted-foreground tabular-nums">
        {data.sku_count} SKU, {data.entry_count} kali hitung
      </p>
      {data.entries.length > 0 && (
        <ul className="mt-3 rounded-xl border bg-card">
          {data.entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center gap-3 border-b py-2 pr-2 pl-4 last:border-b-0"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {skuName(entry)}
                </span>
                <span className="block text-sm text-muted-foreground tabular-nums">
                  {entry.code}
                  {entry.batch_number &&
                    ` · Batch ${entry.batch_number}`} ·{' '}
                  {timeOnly.format(new Date(entry.counted_at))}
                </span>
              </span>
              <span className="font-semibold whitespace-nowrap tabular-nums">
                +{quantity(entry.quantity)} {entry.stock_unit}
              </span>
              {data.can_count && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Batalkan hitungan ${skuName(entry)}`}
                  disabled={undo.isPending}
                  onClick={() =>
                    undo.mutate({ path: { ...path, entry_id: entry.id } })
                  }
                >
                  <Undo2Icon />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
