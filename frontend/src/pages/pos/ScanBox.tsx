import { useMutation } from '@tanstack/react-query'
import { ScanBarcodeIcon } from 'lucide-react'
import { useState } from 'react'
import type { Ref } from 'react'

import { receiptsFindSkus } from '@/client'
import type { TillSku } from '@/client'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { rupiah, skuName } from '@/lib/format'

/** The scanner gun types here and presses Enter; a name works too. */
export function ScanBox({
  onPick,
  inputRef,
}: {
  onPick: (sku: TillSku) => void
  inputRef: Ref<HTMLInputElement>
}) {
  const [text, setText] = useState('')
  const [options, setOptions] = useState<TillSku[] | null>(null)
  const [notFound, setNotFound] = useState<string | null>(null)

  const pick = (sku: TillSku) => {
    onPick(sku)
    setOptions(null)
  }
  const search = useMutation({
    mutationFn: async (query: string) => {
      const { data } = await receiptsFindSkus({
        query: { search: query },
        throwOnError: true,
      })
      return data
    },
    // Scans can overlap: a scanner gun is faster than the server.
    onSuccess: (found, query) => {
      if (found.length === 1) pick(found[0])
      else if (found.length === 0) setNotFound(query)
      else setOptions(found)
    },
  })

  return (
    <div>
      <div className="relative">
        <ScanBarcodeIcon className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setOptions(null)
            setNotFound(null)
          }}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            // Cleared at once, ready for the next scan.
            setText('')
            if (text.trim()) search.mutate(text.trim())
          }}
          placeholder="Scan barcode, atau ketik nama lalu Enter"
          aria-label="Barcode"
          autoComplete="off"
          autoFocus
          className="h-12 bg-card pl-11 text-base"
        />
      </div>
      {search.isError && (
        <p className="mt-2 text-sm text-destructive">
          {errorMessage(search.error)}
        </p>
      )}
      {notFound && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          "{notFound}" tidak ditemukan.
        </p>
      )}
      {options && (
        <ul className="mt-2 max-h-80 overflow-y-auto rounded-xl border bg-card">
          {options.map((option) => (
            <li key={option.id} className="border-b last:border-b-0">
              <button
                type="button"
                onClick={() => pick(option)}
                className="flex w-full items-baseline gap-3 px-3 py-2.5 text-left hover:bg-muted"
              >
                <span className="font-medium">{skuName(option)}</span>
                <span className="ml-auto text-sm text-muted-foreground tabular-nums">
                  {option.code}
                </span>
                <span className="w-24 text-right tabular-nums">
                  {rupiah(option.selling_price)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
