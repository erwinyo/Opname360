import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import {
  reportsDashboardOptions,
  reportsDashboardQueryKey,
  shopSettingsReadSettingsOptions,
} from '@/client/@tanstack/react-query.gen'
import { HourlyChart } from '@/components/HourlyChart'
import { SalesTable } from '@/components/SalesTable'
import { Button } from '@/components/ui/button'
import { errorMessage, queryClient } from '@/lib/api'
import { formatLongDate, formatTime, money, rupiah } from '@/lib/format'
import { useLiveUpdates } from '@/lib/live'
import { hourRange, shownHours } from '@/lib/reports'
import { AttentionList } from '@/pages/reports/Attention'

/** Today so far, updated within seconds of every sale, return and Void. */
export function Dashboard() {
  const shop = useQuery(shopSettingsReadSettingsOptions())
  const dashboard = useQuery(reportsDashboardOptions())
  const [asTable, setAsTable] = useState(false)
  useLiveUpdates(() =>
    queryClient.invalidateQueries({ queryKey: reportsDashboardQueryKey() }),
  )

  if (dashboard.isPending) {
    return <p className="text-muted-foreground">Memuat dasbor…</p>
  }
  if (dashboard.isError) {
    return <p className="text-destructive">{errorMessage(dashboard.error)}</p>
  }
  const today = dashboard.data.today
  const hours = shownHours(today.hours, shop.data)
  const margin =
    today.net_sales > 0
      ? Math.round((Number(today.gross_profit) / today.net_sales) * 100)
      : null

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dasbor</h1>
          <p className="mt-1 text-muted-foreground">
            Hari ini, {formatLongDate(today.day)}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          Diperbarui otomatis · {formatTime(dashboard.dataUpdatedAt)}
        </p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-[1.4fr_1fr_1fr]">
        <div className="col-span-2 rounded-xl border bg-card p-4 sm:col-span-1">
          <p className="text-sm text-muted-foreground">Penjualan bersih</p>
          <p
            className="mt-1 text-5xl font-semibold tracking-tight"
            data-testid="net-sales"
          >
            {rupiah(today.net_sales)}
          </p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">Laba kotor</p>
          <p
            className="mt-1 text-xl font-semibold sm:text-2xl"
            data-testid="gross-profit"
          >
            {money(today.gross_profit ?? 0)}
          </p>
          {margin !== null && (
            <p className="text-sm text-muted-foreground">
              {margin}% dari penjualan bersih
            </p>
          )}
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">Struk</p>
          <p
            className="mt-1 text-xl font-semibold sm:text-2xl"
            data-testid="receipts"
          >
            {today.receipt_count}
          </p>
          <p className="text-sm text-muted-foreground">
            HPP {money(today.cogs ?? 0)}
          </p>
        </div>
      </div>

      <AttentionList attention={dashboard.data.attention} />

      <div className="mt-3 rounded-xl border bg-card p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-medium">Per jam</h2>
          <div className="flex gap-1" role="group" aria-label="Tampilan">
            {[false, true].map((table) => (
              <Button
                key={String(table)}
                size="sm"
                variant={asTable === table ? 'secondary' : 'ghost'}
                aria-pressed={asTable === table}
                onClick={() => setAsTable(table)}
              >
                {table ? 'Tabel' : 'Grafik'}
              </Button>
            ))}
          </div>
        </div>
        <div className="mt-3">
          {today.receipt_count === 0 && Number(today.cogs) === 0 ? (
            <p className="py-10 text-center text-muted-foreground">
              Belum ada penjualan hari ini.
            </p>
          ) : asTable ? (
            <SalesTable
              title="Jam"
              total={today}
              lines={hours.map((hour) => ({
                key: String(hour.hour),
                label: hourRange(hour.hour),
                figures: hour,
              }))}
            />
          ) : (
            <HourlyChart hours={hours} />
          )}
        </div>
      </div>
    </section>
  )
}
