import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, PrinterIcon } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'

import type { UserPublic } from '@/client'
import {
  receiptsReadReceiptOptions,
  shopSettingsReadSettingsOptions,
} from '@/client/@tanstack/react-query.gen'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'

import { ReceiptSlip } from './ReceiptSlip'
import { usePrintReceipt } from './usePrintReceipt'

/** One Receipt as printed, from the Stock Card or the till. */
export function ReceiptPage({ user }: { user: UserPublic }) {
  const receiptId = Number(useParams().receiptId)
  const navigate = useNavigate()
  const receipt = useQuery(
    receiptsReadReceiptOptions({ path: { receipt_id: receiptId } }),
  )
  const shop = useQuery(shopSettingsReadSettingsOptions())
  const printer = usePrintReceipt()
  const canPrint = user.role !== 'admin'

  return (
    <>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" />
        Kembali
      </button>
      {receipt.isPending && (
        <p className="mt-4 text-muted-foreground">Memuat…</p>
      )}
      {receipt.isError && (
        <p className="mt-4 text-destructive">{errorMessage(receipt.error)}</p>
      )}
      {receipt.data && (
        <>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Struk {receipt.data.number}
            </h1>
            {canPrint && (
              <Button
                variant="outline"
                disabled={printer.printing}
                onClick={() => printer.print(receiptId)}
              >
                <PrinterIcon />
                Cetak ulang
              </Button>
            )}
          </div>
          <div className="mt-6 w-fit rounded-xl border bg-white p-4 font-mono text-sm text-black shadow-sm">
            <div className="w-[72mm]">
              <ReceiptSlip receipt={receipt.data} shop={shop.data} />
            </div>
          </div>
        </>
      )}
      {printer.slip}
    </>
  )
}
