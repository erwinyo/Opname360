import { useQuery } from '@tanstack/react-query'

import type { AccountPublic } from '@/client'
import { ledgerListAccountsOptions } from '@/client/@tanstack/react-query.gen'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { money } from '@/lib/format'

/** An account picker: "1101 Kas Besar". */
export function AccountSelect({
  id,
  value,
  onChange,
  filter = () => true,
  placeholder = 'Pilih akun',
  label,
}: {
  id?: string
  value: string
  onChange: (value: string) => void
  filter?: (account: AccountPublic) => boolean
  placeholder?: string
  label?: string
}) {
  const accounts = useQuery(ledgerListAccountsOptions())
  const choices = accounts.data?.filter(
    (account) =>
      (account.is_active && filter(account)) || String(account.id) === value,
  )
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full bg-card" aria-label={label}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {choices?.map((account) => (
          <SelectItem key={account.id} value={String(account.id)}>
            {account.code} {account.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** A debit or credit cell: blank when zero. */
export function Amount({ value }: { value: string | number }) {
  return <>{Number(value) === 0 ? '' : money(value)}</>
}
