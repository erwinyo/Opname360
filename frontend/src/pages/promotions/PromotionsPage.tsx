import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import type { PromotionPublic, PromotionStatus } from '@/client'
import {
  promotionsEndPromotionMutation,
  promotionsListPromotionsOptions,
  promotionsListPromotionsQueryKey,
} from '@/client/@tanstack/react-query.gen'
import { FormDialog } from '@/components/FormDialog'
import { Pager } from '@/components/Pager'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/format'
import { PROMOTION_STATUS_LABELS, TARGET_KIND_LABELS } from '@/lib/labels'

const PAGE_SIZE = 50
const ALL = 'all'

function discountLabel(promotion: {
  discount_kind: string
  value: number
}): string {
  return promotion.discount_kind === 'percentage'
    ? `${promotion.value}%`
    : `${rupiah(promotion.value)} / pcs`
}

function targetSummary(promotion: PromotionPublic): string {
  const labels = promotion.targets.map((target) => target.label)
  const more = labels.length - 2
  return `${TARGET_KIND_LABELS[promotion.target_kind]}: ${labels.slice(0, 2).join(', ')}${more > 0 ? ` dan ${more} lagi` : ''}`
}

export function PromotionsPage() {
  const [status, setStatus] = useState<PromotionStatus | null>('running')
  const [offset, setOffset] = useState(0)
  const [ending, setEnding] = useState<PromotionPublic | null>(null)
  const promotions = useQuery({
    ...promotionsListPromotionsOptions({
      query: { status, offset, limit: PAGE_SIZE },
    }),
    placeholderData: keepPreviousData,
  })
  const end = useMutation({
    ...promotionsEndPromotionMutation(),
    onSuccess: (promotion) => {
      queryClient.invalidateQueries({
        queryKey: promotionsListPromotionsQueryKey(),
      })
      toast.success(`Promo ${promotion.name} diakhiri.`)
      setEnding(null)
    },
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Promo</h1>
          <p className="mt-1 text-muted-foreground">
            Diskon berlaku sendiri di kasir selama periodenya. Bila beberapa
            promo cocok, yang diskonnya terbesar yang dipakai.
          </p>
        </div>
        <Button asChild>
          <Link to="/promo/baru">
            <PlusIcon />
            Buat promo
          </Link>
        </Button>
      </div>

      <div className="mt-6">
        <Select
          value={status ?? ALL}
          onValueChange={(picked) => {
            setStatus(picked === ALL ? null : (picked as PromotionStatus))
            setOffset(0)
          }}
        >
          <SelectTrigger className="bg-card" aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(PROMOTION_STATUS_LABELS) as PromotionStatus[]).map(
              (value) => (
                <SelectItem key={value} value={value}>
                  {PROMOTION_STATUS_LABELS[value]}
                </SelectItem>
              ),
            )}
            <SelectItem value={ALL}>Semua</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {promotions.isError && (
        <p className="mt-6 text-destructive">
          {errorMessage(promotions.error)}
        </p>
      )}
      {promotions.data?.total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          Tidak ada promo di sini.
        </p>
      )}
      {promotions.data && promotions.data.total > 0 && (
        <>
          <ul className="mt-4 grid gap-3">
            {promotions.data.items.map((promotion) => (
              <li
                key={promotion.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-xl border bg-card p-4"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/promo/${promotion.id}`}
                      className="font-medium hover:underline"
                    >
                      {promotion.name}
                    </Link>
                    <Badge
                      variant={
                        promotion.status === 'running' ? 'default' : 'outline'
                      }
                    >
                      {PROMOTION_STATUS_LABELS[promotion.status]}
                    </Badge>
                  </div>
                  <p className="mt-1 text-lg font-semibold tabular-nums">
                    {discountLabel(promotion)}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {targetSummary(promotion)}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {formatDateTime(promotion.starts_at)} –{' '}
                    {formatDateTime(promotion.ends_at)}
                  </p>
                </div>
                {promotion.status !== 'ended' && (
                  <Button
                    variant="outline"
                    onClick={() => setEnding(promotion)}
                  >
                    Akhiri sekarang
                  </Button>
                )}
              </li>
            ))}
          </ul>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={promotions.data.total}
            unit="promo"
            onChange={setOffset}
          />
        </>
      )}

      {ending && (
        <FormDialog
          title={`Akhiri promo ${ending.name}?`}
          description="Promo berhenti saat ini juga dan tidak bisa dijalankan lagi."
          submitLabel="Akhiri"
          destructive
          pending={end.isPending}
          error={end.error}
          onSubmit={() => end.mutate({ path: { promotion_id: ending.id } })}
          onClose={() => {
            end.reset()
            setEnding(null)
          }}
        />
      )}
    </>
  )
}
