import type { FormEvent, ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/lib/api'

/** A labelled form control with its hint, replaced by the error when there is one. */
export function Field({
  id,
  label,
  hint,
  error,
  className,
  children,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={className}>
      <div className="grid gap-2">
        <Label htmlFor={id}>{label}</Label>
        {children}
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : (
          hint && <p className="text-sm text-muted-foreground">{hint}</p>
        )}
      </div>
    </div>
  )
}

/**
 * A dialog that is one small form, or (without children) a confirmation.
 * Mount it to open it; it calls `onClose` when dismissed.
 */
export function FormDialog({
  title,
  description,
  submitLabel,
  pending,
  error,
  destructive,
  onSubmit,
  onClose,
  children,
}: {
  title: string
  description?: string
  submitLabel: string
  pending: boolean
  error: unknown
  destructive?: boolean
  onSubmit: () => void
  onClose: () => void
  children?: ReactNode
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    // Don't let this reach a form the dialog was opened from.
    event.stopPropagation()
    onSubmit()
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-5" noValidate>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && (
              <DialogDescription>{description}</DialogDescription>
            )}
          </DialogHeader>
          {children}
          {error != null && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Batal
            </Button>
            <Button
              type="submit"
              variant={destructive ? 'destructive' : 'default'}
              disabled={pending}
            >
              {pending ? 'Menyimpan…' : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
