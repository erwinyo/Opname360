import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import type { Cart, PaymentMethodPublic, ReceiptPublic } from '@/client'
import {
  paymentMethodsListMethodsOptions,
  receiptsCompleteReceiptMutation,
} from '@/client/@tanstack/react-query.gen'
import { FormDialog } from '@/components/FormDialog'
import { MoneyInput } from '@/components/MoneyInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { queryClient } from '@/lib/api'
import { rupiah } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Cash amounts a customer is likely to hand over for `due`. */
function cashSuggestions(due: number): number[] {
  const rounded = [50000, 100000].map((note) => Math.ceil(due / note) * note)
  return [...new Set([due, ...rounded])].filter((amount) => amount > 0)
}

/** Payment, split over methods if needed; change only from cash (rule 8). */
export function PayDialog({
  total,
  cart,
  onClose,
  onPaid,
}: {
  total: number
  cart: Cart
  onClose: () => void
  onPaid: (receipt: ReceiptPublic) => void
}) {
  const methods = useQuery(
    paymentMethodsListMethodsOptions({ query: { active_only: true } }),
  )
  const [amounts, setAmounts] = useState<Record<number, string>>({})
  const [references, setReferences] = useState<Record<number, string>>({})
  const [confirmed, setConfirmed] = useState<Record<number, boolean>>({})
  const [checked, setChecked] = useState(false)
  const complete = useMutation({
    ...receiptsCompleteReceiptMutation(),
    onSuccess: onPaid,
    // A price or Promotion may have changed: show the cart's new total.
    onError: () => queryClient.invalidateQueries({ queryKey: ['quote'] }),
  })

  const list = methods.data ?? []
  const amount = (method: PaymentMethodPublic) =>
    Number(amounts[method.id] || 0)
  const paid = list.reduce((sum, method) => sum + amount(method), 0)
  const nonCash = list
    .filter((method) => !method.is_cash)
    .reduce((sum, method) => sum + amount(method), 0)
  const change = paid - total
  const unconfirmed = list.filter(
    (method) => !method.is_cash && amount(method) > 0 && !confirmed[method.id],
  )
  const problem =
    nonCash > total
      ? 'Non-tunai melebihi total: kembalian hanya dari uang tunai.'
      : unconfirmed.length > 0
        ? `Centang bila ${unconfirmed.map((m) => m.name).join(', ')} sudah masuk.`
        : change < 0
          ? `Kurang ${rupiah(-change)}.`
          : undefined
  const set = (method: PaymentMethodPublic, value: number | string) =>
    setAmounts((current) => ({ ...current, [method.id]: String(value) }))
  const others = (method: PaymentMethodPublic) => paid - amount(method)

  const submit = () => {
    setChecked(true)
    if (problem) return
    complete.mutate({
      body: {
        ...cart,
        expected_total: total,
        payments: list
          .filter((method) => amount(method) > 0)
          .map((method) => ({
            payment_method_id: method.id,
            amount: amount(method),
            reference: references[method.id]?.trim() || null,
            confirmed: Boolean(confirmed[method.id]),
          })),
      },
    })
  }

  return (
    <FormDialog
      title={`Bayar ${rupiah(total)}`}
      submitLabel="Selesai"
      pending={complete.isPending}
      error={complete.error}
      onSubmit={submit}
      onClose={onClose}
    >
      {total > 0 && (
        <div className="grid gap-4">
          {list.map((method, index) => (
            <div key={method.id} className="grid gap-2">
              <div className="flex items-center gap-3">
                <label
                  htmlFor={`pay-${method.id}`}
                  className="w-28 shrink-0 font-medium"
                >
                  {method.name}
                </label>
                <MoneyInput
                  id={`pay-${method.id}`}
                  value={amounts[method.id] ?? ''}
                  onValueChange={(digits) => set(method, digits)}
                  autoFocus={index === 0}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 pl-31">
                {method.is_cash ? (
                  cashSuggestions(Math.max(total - others(method), 0)).map(
                    (suggestion, n) => (
                      <Button
                        key={suggestion}
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => set(method, suggestion)}
                      >
                        {n === 0 ? 'Uang pas' : rupiah(suggestion)}
                      </Button>
                    ),
                  )
                ) : (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        set(method, Math.max(total - others(method), 0))
                      }
                    >
                      Sisanya
                    </Button>
                    {amount(method) > 0 && (
                      <>
                        <Input
                          value={references[method.id] ?? ''}
                          onChange={(event) =>
                            setReferences((current) => ({
                              ...current,
                              [method.id]: event.target.value,
                            }))
                          }
                          placeholder="No. referensi (opsional)"
                          aria-label={`Referensi ${method.name}`}
                          maxLength={100}
                          className="h-8 w-48"
                        />
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={Boolean(confirmed[method.id])}
                            onChange={(event) =>
                              setConfirmed((current) => ({
                                ...current,
                                [method.id]: event.target.checked,
                              }))
                            }
                            className="size-4 accent-primary"
                          />
                          {method.name} sudah masuk
                        </label>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <dl className="grid grid-cols-[1fr_auto] gap-y-1 rounded-lg bg-muted p-3 text-lg tabular-nums">
        <dt>Dibayar</dt>
        <dd className="text-right">{rupiah(paid)}</dd>
        <dt className={cn('font-semibold', change < 0 && 'text-destructive')}>
          {change < 0 ? 'Kurang' : 'Kembali'}
        </dt>
        <dd
          className={cn(
            'text-right font-semibold',
            change < 0 && 'text-destructive',
          )}
        >
          {rupiah(Math.abs(change))}
        </dd>
      </dl>
      {checked && problem && !complete.isError && (
        <p className="text-sm text-destructive">{problem}</p>
      )}
    </FormDialog>
  )
}
