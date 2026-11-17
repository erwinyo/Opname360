import type { ComponentProps } from 'react'

import { Input } from '@/components/ui/input'
import { groupDigits, onlyDigits } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Whole rupiah, grouped as you type. `value` holds the digits only. */
export function MoneyInput({
  value,
  onValueChange,
  className,
  ...props
}: Omit<ComponentProps<typeof Input>, 'value' | 'onChange'> & {
  value: string
  onValueChange: (digits: string) => void
}) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-sm text-muted-foreground">
        Rp
      </span>
      <Input
        {...props}
        value={groupDigits(value)}
        onChange={(event) => onValueChange(onlyDigits(event.target.value))}
        inputMode="numeric"
        autoComplete="off"
        className={cn('pl-9 text-right tabular-nums', className)}
      />
    </div>
  )
}
