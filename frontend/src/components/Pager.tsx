import { Button } from '@/components/ui/button'

/** "1–50 dari 123 produk" with previous and next buttons. */
export function Pager({
  offset,
  pageSize,
  total,
  unit,
  onChange,
}: {
  offset: number
  pageSize: number
  total: number
  unit: string
  onChange: (offset: number) => void
}) {
  if (total === 0) return null
  return (
    <div className="mt-3 flex items-center justify-between gap-4 text-sm text-muted-foreground">
      <span className="tabular-nums">
        {offset + 1}–{Math.min(offset + pageSize, total)} dari {total} {unit}
      </span>
      {total > pageSize && (
        <span className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0}
            onClick={() => onChange(Math.max(offset - pageSize, 0))}
          >
            Sebelumnya
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + pageSize >= total}
            onClick={() => onChange(offset + pageSize)}
          >
            Berikutnya
          </Button>
        </span>
      )}
    </div>
  )
}
