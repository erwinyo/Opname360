import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import {
  ledgerReadLockDateOptions,
  ledgerReadLockDateQueryKey,
  ledgerSetLockDateMutation,
} from '@/client/@tanstack/react-query.gen'
import { Field } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { daysAgo } from '@/lib/reports'

/** Tutup Periode (Owner): nothing is posted on or before the lock date. */
export function LockDatePage() {
  const current = useQuery(ledgerReadLockDateOptions())
  const [day, setDay] = useState('')
  const save = useMutation({
    ...ledgerSetLockDateMutation(),
    onSuccess: (saved) => {
      queryClient.setQueryData(ledgerReadLockDateQueryKey(), saved)
      setDay('')
      toast.success(
        saved.lock_date
          ? `Pembukuan ditutup sampai ${formatDate(saved.lock_date)}.`
          : 'Semua periode dibuka.',
      )
    },
  })
  const locked = current.data?.lock_date
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Tutup Periode</h1>
      <p className="mt-1 max-w-2xl text-muted-foreground">
        Setelah periode ditutup, tidak ada jurnal yang bisa dibuat pada atau
        sebelum tanggal tutupnya, termasuk kas keluar, pindah kas, bayar hutang,
        dan jurnal umum bertanggal mundur.
      </p>
      <p className="mt-6 text-lg">
        {locked ? (
          <>
            Ditutup sampai <strong>{formatDate(locked)}</strong>.
          </>
        ) : (
          'Belum ada periode yang ditutup.'
        )}
      </p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <Field id="lock-date" label="Tutup sampai tanggal">
          <Input
            id="lock-date"
            type="date"
            value={day}
            max={daysAgo(1)}
            onChange={(event) => setDay(event.target.value)}
          />
        </Field>
        <Button
          disabled={!day || save.isPending}
          onClick={() => save.mutate({ body: { lock_date: day } })}
        >
          Tutup periode
        </Button>
        {locked && (
          <Button
            variant="outline"
            disabled={save.isPending}
            onClick={() => save.mutate({ body: { lock_date: null } })}
          >
            Buka semua periode
          </Button>
        )}
      </div>
      {save.isError && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
    </>
  )
}
