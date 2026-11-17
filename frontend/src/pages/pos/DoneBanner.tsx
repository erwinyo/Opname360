import { CheckCircle2Icon, PrinterIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { ReceiptPublic } from '@/client'
import { Button } from '@/components/ui/button'
import { rupiah } from '@/lib/format'

/** The Receipt just completed: what to hand back, and a reprint. */
export function DoneBanner({
  receipt,
  printing,
  onReprint,
}: {
  receipt: ReceiptPublic
  printing: boolean
  onReprint: () => void
}) {
  const handBack =
    receipt.total < 0
      ? `Kembalikan ${rupiah(-receipt.total)}`
      : receipt.change_given > 0
        ? `Kembali ${rupiah(receipt.change_given)}`
        : null
  return (
    <div
      role="status"
      className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-primary/40 bg-primary/5 p-4"
    >
      <CheckCircle2Icon className="size-6 text-primary" />
      <div>
        <p className="font-medium">
          Struk{' '}
          <Link to={`/struk/${receipt.id}`} className="text-primary underline">
            {receipt.number}
          </Link>{' '}
          selesai.
        </p>
        <p className="text-sm text-muted-foreground">
          {receipt.total < 0
            ? `${receipt.payments[0]?.method_name ?? 'Tunai'}`
            : `Total ${rupiah(receipt.total)}`}
        </p>
      </div>
      {handBack && (
        <p className="text-2xl font-semibold tabular-nums">{handBack}</p>
      )}
      <Button
        variant="outline"
        className="ml-auto"
        disabled={printing}
        onClick={onReprint}
      >
        <PrinterIcon />
        Cetak ulang
      </Button>
    </div>
  )
}
