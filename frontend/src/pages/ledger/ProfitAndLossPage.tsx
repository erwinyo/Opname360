import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PrinterIcon } from 'lucide-react'
import { useState } from 'react'

import type { ProfitAndLoss } from '@/client'
import { ledgerProfitAndLossOptions } from '@/client/@tanstack/react-query.gen'
import { A4Print } from '@/components/A4Print'
import { DateInput, Filters, ReportHeader } from '@/components/reports'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import { formatDate, money, today } from '@/lib/format'
import { withQuery } from '@/lib/reports'

import { StatementGroup, StatementRow } from './statements'

/** Laba Rugi for a period (rule 14). */
export function ProfitAndLossPage() {
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const report = useQuery({
    ...ledgerProfitAndLossOptions({ query: { start, end } }),
    placeholderData: keepPreviousData,
  })
  return (
    <>
      <ReportHeader
        title="Laba Rugi"
        description="Penjualan bersih, harga pokok, laba kotor, beban, dan laba bersih dalam satu periode."
        excel={withQuery('ledger/profit-and-loss/excel', { start, end })}
      />
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
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
          <div className="mt-4 max-w-2xl rounded-xl border bg-card p-4 sm:p-6">
            <Statement report={report.data} />
          </div>
          <A4Print>
            <h1 className="text-xl font-bold">Laba Rugi</h1>
            <p className="mb-4">
              {formatDate(report.data.start)} s.d. {formatDate(report.data.end)}
            </p>
            <Statement report={report.data} />
          </A4Print>
        </>
      )}
    </>
  )
}

function Statement({ report }: { report: ProfitAndLoss }) {
  return (
    <>
      <StatementGroup
        title="Pendapatan usaha"
        lines={report.sales}
        total={report.net_sales}
        totalLabel="Penjualan bersih"
      />
      <StatementGroup
        title="Harga pokok penjualan"
        lines={report.cogs}
        total={report.total_cogs}
        totalLabel="Jumlah HPP"
      />
      <div className="mt-4 rounded-md bg-muted/60 px-2">
        <StatementRow label="Laba kotor" strong>
          {money(report.gross_profit)}
        </StatementRow>
      </div>
      <StatementGroup
        title="Beban"
        lines={report.expenses}
        total={report.total_expenses}
        totalLabel="Jumlah beban"
      />
      <StatementGroup
        title="Pendapatan lain"
        lines={report.other_income}
        total={report.total_other_income}
        totalLabel="Jumlah pendapatan lain"
      />
      <div className="mt-4 rounded-md bg-muted/60 px-2 text-lg">
        <StatementRow label="Laba bersih" strong>
          {money(report.net_profit)}
        </StatementRow>
      </div>
    </>
  )
}
