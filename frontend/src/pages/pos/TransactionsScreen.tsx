import type { ShiftCurrent } from '@/client'

import { ReceiptList } from './ReceiptList'
import { ShiftBar } from './ShiftBar'

/** The open Shift's Receipts: reprint, or void with a reason. */
export function TransactionsScreen({ shift }: { shift: ShiftCurrent }) {
  return (
    <>
      <ShiftBar shift={shift} />
      <p className="mt-4 text-sm text-muted-foreground">
        Struk hanya bisa dibatalkan selama shift ini masih terbuka. Setelah
        tutup shift, gunakan retur.
      </p>
      <div className="mt-3">
        <ReceiptList shiftId={shift.id} actions />
      </div>
    </>
  )
}
