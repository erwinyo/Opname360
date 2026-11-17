import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import {
  reportsHourlyOptions,
  shopSettingsReadSettingsOptions,
} from '@/client/@tanstack/react-query.gen'
import { HourlyChart } from '@/components/HourlyChart'
import { DateInput, Empty, Filters, ReportHeader } from '@/components/reports'
import { SalesTable } from '@/components/SalesTable'
import { errorMessage } from '@/lib/api'
import { today } from '@/lib/format'
import { hourRange, shownHours, withQuery } from '@/lib/reports'

export function HourlyPage() {
  const [day, setDay] = useState(today)
  const shop = useQuery(shopSettingsReadSettingsOptions())
  const report = useQuery({
    ...reportsHourlyOptions({ query: { day } }),
    placeholderData: keepPreviousData,
  })
  const data = report.data
  const hours = data ? shownHours(data.hours, shop.data) : []

  return (
    <>
      <ReportHeader
        title="Laba Kotor per Jam"
        description="Penjualan bersih, HPP, dan laba kotor tiap jam dalam satu hari. Belum dikurangi biaya."
        excel={withQuery('reports/hourly/excel', { day })}
      />
      <Filters>
        <DateInput label="Tanggal" value={day} onChange={setDay} />
      </Filters>
      {report.isError && (
        <p className="mt-6 text-destructive">{errorMessage(report.error)}</p>
      )}
      {data && data.receipt_count === 0 && Number(data.cogs) === 0 && (
        <Empty>Belum ada penjualan pada hari itu.</Empty>
      )}
      {data && (data.receipt_count > 0 || Number(data.cogs) !== 0) && (
        <>
          <section className="mt-4 rounded-xl border bg-card p-4">
            <HourlyChart hours={hours} />
          </section>
          <div className="mt-4">
            <SalesTable
              title="Jam"
              total={data}
              lines={hours.map((hour) => ({
                key: String(hour.hour),
                label: hourRange(hour.hour),
                figures: hour,
              }))}
            />
          </div>
        </>
      )}
    </>
  )
}
