import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'

import {
  shiftsCloseShiftMutation,
  shiftsReadCurrentOptions,
  shiftsReadCurrentQueryKey,
} from '@/client/@tanstack/react-query.gen'
import { BackLink } from '@/components/documents'
import { Field, FormDialog } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Button } from '@/components/ui/button'
import { errorMessage, queryClient } from '@/lib/api'
import { rupiah } from '@/lib/format'

/** The blind cash count: the expected amount shows only afterwards. */
export function CloseShiftPage() {
  const navigate = useNavigate()
  const current = useQuery(shiftsReadCurrentOptions())
  const [counted, setCounted] = useState('')
  const [checked, setChecked] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const close = useMutation({
    ...shiftsCloseShiftMutation(),
    onSuccess: (shift) => {
      queryClient.setQueryData(shiftsReadCurrentQueryKey(), null)
      navigate(`/shift/${shift.id}`)
    },
  })

  if (current.isPending) return <p className="text-muted-foreground">Memuat…</p>
  const shift = current.data
  if (!shift?.is_mine) return <Navigate to="/kasir" replace />

  const countedError = counted === '' ? 'Isi jumlah uang di laci.' : undefined
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (!countedError) setConfirming(true)
  }

  return (
    <form onSubmit={submit} noValidate className="max-w-sm">
      <BackLink to="/kasir" label="Kasir" />
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        Tutup Shift {shift.number}
      </h1>
      <p className="mt-1 text-muted-foreground">
        Hitung semua uang tunai di laci, termasuk modal kas. Seluruh uang
        diserahkan; shift berikutnya mulai dengan modal kas baru.
      </p>
      <Field
        id="counted-cash"
        label="Uang tunai di laci"
        error={checked ? countedError : undefined}
        className="mt-6"
      >
        <MoneyInput
          id="counted-cash"
          value={counted}
          onValueChange={setCounted}
          autoFocus
        />
      </Field>
      <Button type="submit" className="mt-6">
        Tutup shift
      </Button>
      {confirming && (
        <FormDialog
          title={`Tutup shift dengan ${rupiah(Number(counted))}?`}
          description="Setelah ditutup, shift tidak bisa dibuka lagi dan tidak ada penjualan sampai shift baru dibuka."
          submitLabel="Tutup shift"
          pending={close.isPending}
          error={close.error}
          onSubmit={() =>
            close.mutate({
              path: { shift_id: shift.id },
              body: { counted_cash: Number(counted) },
            })
          }
          onClose={() => {
            close.reset()
            setConfirming(false)
          }}
        />
      )}
      {close.isError && !confirming && (
        <p role="alert" className="mt-4 text-destructive">
          {errorMessage(close.error)}
        </p>
      )}
    </form>
  )
}
