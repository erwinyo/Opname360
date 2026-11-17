import { useMutation, useQuery } from '@tanstack/react-query'
import { LockIcon } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'

import type { ShiftCurrent } from '@/client'
import {
  shiftsOpenShiftMutation,
  shiftsReadCurrentOptions,
  shiftsReadCurrentQueryKey,
} from '@/client/@tanstack/react-query.gen'
import { Field } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Button } from '@/components/ui/button'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

/** The till: open a Shift first, then sell in it. */
export function TillPage() {
  const current = useQuery(shiftsReadCurrentOptions())
  if (current.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (current.isError) {
    return <p className="text-destructive">{errorMessage(current.error)}</p>
  }
  const shift = current.data
  if (!shift) return <OpenShift />
  if (!shift.is_mine) return <SomeoneElsesShift shift={shift} />
  return <ShiftBar shift={shift} />
}

export function ShiftBar({ shift }: { shift: ShiftCurrent }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Kasir</h1>
        <p className="text-sm text-muted-foreground">
          Shift {shift.number} · {shift.cashier_name} · sejak{' '}
          {formatDateTime(shift.opened_at)}
        </p>
      </div>
      <Button asChild variant="outline">
        <Link to="/kasir/tutup">
          <LockIcon />
          Tutup shift
        </Link>
      </Button>
    </div>
  )
}

function SomeoneElsesShift({ shift }: { shift: ShiftCurrent }) {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Kasir</h1>
      <p className="mt-6 max-w-md rounded-xl border border-dashed p-4 text-muted-foreground">
        Shift {shift.number} milik {shift.cashier_name} masih terbuka sejak{' '}
        {formatDateTime(shift.opened_at)}. Laci kas hanya satu, jadi kasir ini
        bisa dipakai setelah shift itu ditutup.
      </p>
    </>
  )
}

function OpenShift() {
  const [float, setFloat] = useState('')
  const [checked, setChecked] = useState(false)
  const floatError = float === '' ? 'Isi modal kas, boleh 0.' : undefined
  const open = useMutation({
    ...shiftsOpenShiftMutation(),
    onSuccess: (shift) =>
      queryClient.setQueryData(shiftsReadCurrentQueryKey(), shift),
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setChecked(true)
    if (floatError) return
    open.mutate({ body: { opening_float: Number(float) } })
  }

  return (
    <form onSubmit={submit} noValidate className="max-w-sm">
      <h1 className="text-2xl font-semibold tracking-tight">Buka Shift</h1>
      <p className="mt-1 text-muted-foreground">
        Hitung uang di laci kas sebelum mulai berjualan.
      </p>
      <Field
        id="opening-float"
        label="Modal kas"
        error={checked ? floatError : undefined}
        className="mt-6"
      >
        <MoneyInput
          id="opening-float"
          value={float}
          onValueChange={setFloat}
          autoFocus
        />
      </Field>
      {open.isError && (
        <p role="alert" className="mt-4 text-destructive">
          {errorMessage(open.error)}
        </p>
      )}
      <Button type="submit" className="mt-6" disabled={open.isPending}>
        {open.isPending ? 'Membuka…' : 'Buka shift'}
      </Button>
    </form>
  )
}
