import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PrinterIcon } from 'lucide-react'
import { useState } from 'react'

import type { BalanceSheet } from '@/client'
import { ledgerBalanceSheetOptions } from '@/client/@tanstack/react-query.gen'
import { A4Print } from '@/components/A4Print'
import { DateInput, Filters, ReportHeader } from '@/components/reports'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import { formatDate, money, today } from '@/lib/format'
import { withQuery } from '@/lib/reports'

import { StatementGroup, StatementRow } from './statements'

/** Neraca in T layout: assets left, liabilities and equity right (rule 13). */
export function BalanceSheetPage() {
  const [on, setOn] = useState(today)
  const report = useQuery({
    ...ledgerBalanceSheetOptions({ query: { on } }),
    placeholderData: keepPreviousData,
  })
  return (
    <>
      <ReportHeader
        title="Neraca"
        description="Aset di kiri, kewajiban dan ekuitas di kanan, pada akhir hari yang dipilih. Laba tahun-tahun sebelumnya masuk Laba Ditahan."
        excel={withQuery('ledger/balance-sheet/excel', { on })}
      />
      <Filters>
        <DateInput label="Per tanggal" value={on} onChange={setOn} />
        <Button variant="outline" onClick={() => window.print()}>
          <PrinterIcon />
          Cetak
        </Button>
      </Filters>
      {report.isError && (
        <p className="mt-6 text-destructive">{errorMessage(report.error)}</p>
      )}
      {report.data && (
        <>
          <div className="mt-4 rounded-xl border bg-card p-4 sm:p-6">
            <TAccount report={report.data} />
          </div>
          <A4Print>
            <h1 className="text-xl font-bold">Neraca</h1>
            <p className="mb-4">Per {formatDate(report.data.on)}</p>
            <TAccount report={report.data} print />
          </A4Print>
        </>
      )}
    </>
  )
}

function TAccount({
  report,
  print,
}: {
  report: BalanceSheet
  print?: boolean
}) {
  return (
    <div
      className={
        print
          ? 'grid grid-cols-2 gap-8'
          : 'grid gap-8 md:grid-cols-2 md:gap-0 md:divide-x'
      }
    >
      <div className="flex flex-col md:pr-6">
        <StatementGroup
          title="Aset"
          lines={report.assets}
          total={report.total_assets}
          totalLabel="Jumlah aset"
        />
        <div className="mt-auto pt-4">
          <StatementRow label="Total aset" strong>
            {money(report.total_assets)}
          </StatementRow>
        </div>
      </div>
      <div className="flex flex-col md:pl-6">
        <StatementGroup
          title="Kewajiban"
          lines={report.liabilities}
          total={report.total_liabilities}
          totalLabel="Jumlah kewajiban"
        />
        <StatementGroup
          title="Ekuitas"
          lines={report.equity}
          total={report.total_equity}
          totalLabel="Jumlah ekuitas"
        />
        <div className="mt-auto pt-4">
          <StatementRow label="Total kewajiban dan ekuitas" strong>
            {money(report.total_liabilities_and_equity)}
          </StatementRow>
        </div>
      </div>
    </div>
  )
}
