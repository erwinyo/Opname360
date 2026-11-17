import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { flushSync } from 'react-dom'
import { toast } from 'sonner'

import type { ReceiptPublic } from '@/client'
import {
  receiptsPrintReceiptMutation,
  shopSettingsReadSettingsOptions,
} from '@/client/@tanstack/react-query.gen'
import { ThermalPrint } from '@/components/ThermalPrint'
import { errorMessage } from '@/lib/api'

import { ReceiptSlip } from './ReceiptSlip'

/**
 * Print a Receipt: the server counts the printout first, so every one after
 * the first says SALINAN. Render `slip` somewhere on the page.
 */
export function usePrintReceipt() {
  const shop = useQuery(shopSettingsReadSettingsOptions())
  const [receipt, setReceipt] = useState<ReceiptPublic | null>(null)
  const mutation = useMutation({
    ...receiptsPrintReceiptMutation(),
    onSuccess: (printed) => {
      // The slip must be on the page before the print dialog takes it.
      flushSync(() => setReceipt(printed))
      window.print()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  return {
    print: (receiptId: number) =>
      mutation.mutate({ path: { receipt_id: receiptId } }),
    printing: mutation.isPending,
    slip: receipt && (
      <ThermalPrint>
        <ReceiptSlip receipt={receipt} shop={shop.data} />
      </ThermalPrint>
    ),
  }
}
