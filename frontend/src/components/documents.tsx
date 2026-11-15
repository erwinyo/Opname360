import { ArrowLeftIcon, BanIcon } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { DocumentStatus, ReversalPublic } from '@/client'
import { Field, FormDialog } from '@/components/FormDialog'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime } from '@/lib/format'
import { STATUS_LABELS } from '@/lib/labels'

export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  )
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  if (status === 'reversed') {
    return (
      <Badge variant="destructive">{STATUS_LABELS.reversed}</Badge>
    )
  }
  return (
    <Badge variant={status === 'completed' ? 'secondary' : 'outline'}>
      {STATUS_LABELS[status]}
    </Badge>
  )
}

/** The header facts of a completed document, as a grid of term and value. */
export function Facts({
  facts,
  note,
}: {
  facts: [string, ReactNode][]
  note?: string | null
}) {
  return (
    <dl className="mt-6 grid gap-x-6 gap-y-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-3">
      {facts.map(([term, value]) => (
        <div key={term}>
          <dt className="text-sm text-muted-foreground">{term}</dt>
          <dd className="font-medium">{value}</dd>
        </div>
      ))}
      {note && (
        <div className="sm:col-span-2 lg:col-span-3">
          <dt className="text-sm text-muted-foreground">Catatan</dt>
          <dd>{note}</dd>
        </div>
      )}
    </dl>
  )
}

/** Shown on a reversed document: who cancelled it, when, and why. */
export function ReversalNotice({ reversal }: { reversal: ReversalPublic }) {
  return (
    <div
      role="note"
      className="mt-6 flex gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4"
    >
      <BanIcon className="mt-0.5 size-5 shrink-0 text-destructive" />
      <div>
        <p className="font-medium">
          Dibatalkan dengan{' '}
          <span className="tabular-nums">{reversal.number}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          {reversal.created_by_name ?? 'Sistem'} ·{' '}
          {formatDateTime(reversal.created_at)}
        </p>
        <p className="mt-2">Alasan: {reversal.reason}</p>
      </div>
    </div>
  )
}

/** Asks why a completed document is being cancelled, then cancels it. */
export function ReverseDialog({
  title,
  description,
  pending,
  error,
  onReverse,
  onClose,
}: {
  title: string
  description: string
  pending: boolean
  error: unknown
  onReverse: (reason: string) => void
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [checked, setChecked] = useState(false)
  const reasonError = reason.trim() ? undefined : 'Tulis alasan pembatalan.'
  return (
    <FormDialog
      title={title}
      description={description}
      submitLabel="Batalkan dokumen"
      destructive
      pending={pending}
      error={error}
      onSubmit={() => {
        setChecked(true)
        if (!reasonError) onReverse(reason)
      }}
      onClose={onClose}
    >
      <Field
        id="reversal-reason"
        label="Alasan"
        hint="Tercatat di dokumen dan di log aktivitas."
        error={checked ? reasonError : undefined}
      >
        <Textarea
          id="reversal-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={300}
          autoFocus
        />
      </Field>
    </FormDialog>
  )
}
