import { useMutation, useQuery } from '@tanstack/react-query'
import { EllipsisIcon } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { ReceiptSummary } from '@/client'
import {
  receiptsListReceiptsOptions,
  receiptsListReceiptsQueryKey,
  receiptsVoidReceiptMutation,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage, queryClient } from '@/lib/api'
import { rupiah } from '@/lib/format'
import { RECEIPT_KIND_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

import { usePrintReceipt } from './usePrintReceipt'

const time = new Intl.DateTimeFormat('id-ID', { timeStyle: 'short' })

/**
 * A Shift's Receipts. At the till (`actions`) each can be reprinted, and
 * voided while the Shift is open.
 */
export function ReceiptList({
  shiftId,
  actions,
}: {
  shiftId: number
  actions: boolean
}) {
  const receipts = useQuery(
    receiptsListReceiptsOptions({ query: { shift_id: shiftId, limit: 500 } }),
  )
  const printer = usePrintReceipt()
  const [voiding, setVoiding] = useState<ReceiptSummary | null>(null)

  if (receipts.isError) {
    return <p className="text-destructive">{errorMessage(receipts.error)}</p>
  }
  if (receipts.data?.total === 0) {
    return (
      <p className="rounded-xl border border-dashed p-6 text-muted-foreground">
        Belum ada transaksi di shift ini.
      </p>
    )
  }
  return (
    <>
      <div className="overflow-x-auto rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Jam</TableHead>
              <TableHead>Struk</TableHead>
              <TableHead>Jenis</TableHead>
              <TableHead>Pembayaran</TableHead>
              <TableHead className="text-right">Total</TableHead>
              {actions && (
                <TableHead className="w-0">
                  <span className="sr-only">Tindakan</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {receipts.data?.items.map((receipt) => {
              const voided = receipt.status === 'voided'
              return (
                <TableRow
                  key={receipt.id}
                  className={cn(voided && 'text-muted-foreground')}
                >
                  <TableCell className="tabular-nums">
                    {time.format(new Date(receipt.created_at))}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/struk/${receipt.id}`}
                      className={cn(
                        'font-medium text-primary tabular-nums hover:underline',
                        voided && 'line-through',
                      )}
                    >
                      {receipt.number}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {RECEIPT_KIND_LABELS[receipt.kind]}
                    {voided && (
                      <Badge variant="destructive" className="ml-2">
                        Dibatalkan
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{receipt.methods || '–'}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {rupiah(receipt.total)}
                  </TableCell>
                  {actions && (
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Tindakan untuk ${receipt.number}`}
                          >
                            <EllipsisIcon />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onSelect={() => printer.print(receipt.id)}
                          >
                            Cetak ulang
                          </DropdownMenuItem>
                          {!voided && (
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => setVoiding(receipt)}
                            >
                              Batalkan struk
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {voiding && (
        <VoidDialog receipt={voiding} onClose={() => setVoiding(null)} />
      )}
      {printer.slip}
    </>
  )
}

function VoidDialog({
  receipt,
  onClose,
}: {
  receipt: ReceiptSummary
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [checked, setChecked] = useState(false)
  const reasonError = reason.trim() ? undefined : 'Alasan wajib diisi.'
  const voidReceipt = useMutation({
    ...receiptsVoidReceiptMutation(),
    onSuccess: (voided) => {
      queryClient.invalidateQueries({
        queryKey: receiptsListReceiptsQueryKey({
          query: { shift_id: voided.shift_id, limit: 500 },
        }),
      })
      toast.success(`Struk ${voided.number} dibatalkan.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Batalkan struk ${receipt.number}?`}
      description={`Stok kembali seperti sebelum transaksi, dan ${
        receipt.total < 0 ? 'uang yang dikembalikan' : 'pembayarannya'
      } (${rupiah(Math.abs(receipt.total))}) tidak lagi dihitung di laci.`}
      submitLabel="Batalkan struk"
      destructive
      pending={voidReceipt.isPending}
      error={voidReceipt.error}
      onSubmit={() => {
        setChecked(true)
        if (reasonError) return
        voidReceipt.mutate({
          path: { receipt_id: receipt.id },
          body: { reason },
        })
      }}
      onClose={onClose}
    >
      <Field
        id="void-reason"
        label="Alasan"
        error={checked ? reasonError : undefined}
      >
        <Textarea
          id="void-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={300}
          autoFocus
        />
      </Field>
    </FormDialog>
  )
}
