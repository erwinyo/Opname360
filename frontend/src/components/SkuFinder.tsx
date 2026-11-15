import { useMutation } from '@tanstack/react-query'
import { ScanBarcodeIcon } from 'lucide-react'
import { useRef, useState } from 'react'

import { productsSearchSkus } from '@/client'
import type { SkuOption } from '@/client'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { variantLabel } from '@/lib/format'

/** Scan a Barcode or type part of a name; one match is added straight away. */
export function SkuFinder({ onPick }: { onPick: (option: SkuOption) => void }) {
  const [text, setText] = useState('')
  const [options, setOptions] = useState<SkuOption[] | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const pick = (option: SkuOption) => {
    onPick(option)
    setText('')
    setOptions(null)
    input.current?.focus()
  }
  const search = useMutation({
    mutationFn: async (query: string) => {
      const { data } = await productsSearchSkus({
        query: { query },
        throwOnError: true,
      })
      return data
    },
    onSuccess: (found) => {
      if (found.length === 1) pick(found[0])
      else setOptions(found)
    },
  })

  return (
    <div className="mt-3">
      <div className="relative">
        <ScanBarcodeIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={input}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setOptions(null)
          }}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            // Enter here looks for a SKU; it must not save the form.
            event.preventDefault()
            if (text.trim()) search.mutate(text)
          }}
          placeholder="Scan barcode, atau ketik nama lalu Enter"
          aria-label="Tambah barang"
          className="bg-card pl-8"
        />
      </div>
      {search.isError && (
        <p className="mt-2 text-sm text-destructive">
          {errorMessage(search.error)}
        </p>
      )}
      {options?.length === 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          Tidak ada barang yang cocok dengan "{text}".
        </p>
      )}
      {options && options.length > 1 && (
        <ul className="mt-2 rounded-xl border bg-card">
          {options.map((option) => (
            <li key={option.id} className="border-b last:border-b-0">
              <button
                type="button"
                onClick={() => pick(option)}
                className="flex w-full items-baseline gap-3 px-3 py-2 text-left hover:bg-muted"
              >
                <span className="font-medium">
                  {[option.product_name, variantLabel(option)]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
                <span className="ml-auto text-sm text-muted-foreground tabular-nums">
                  {option.code} · {option.barcode}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
