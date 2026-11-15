import type { DocumentStatus } from '@/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { STATUS_LABELS } from '@/lib/labels'

const ALL = 'all'

/** Filter a document list by status; `null` means every status. */
export function StatusFilter({
  value,
  onChange,
}: {
  value: DocumentStatus | null
  onChange: (status: DocumentStatus | null) => void
}) {
  return (
    <div className="mt-6">
      <Select
        value={value ?? ALL}
        onValueChange={(picked) =>
          onChange(picked === ALL ? null : (picked as DocumentStatus))
        }
      >
        <SelectTrigger className="bg-card" aria-label="Status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Semua status</SelectItem>
          {(Object.keys(STATUS_LABELS) as DocumentStatus[]).map((status) => (
            <SelectItem key={status} value={status}>
              {STATUS_LABELS[status]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
