import { useQuery } from '@tanstack/react-query'
import { PrinterIcon } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useParams } from 'react-router'

import type { OpnameLinePublic, OpnamePublic } from '@/client'
import {
  opnamesListLinesOptions,
  opnamesReadOpnameOptions,
} from '@/client/@tanstack/react-query.gen'
import { BackLink } from '@/components/documents'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import {
  batchLabel,
  formatDateTime,
  money,
  quantity,
  rupiah,
  skuName,
} from '@/lib/format'
import { RESOLUTION_LABELS, SHORTAGE_REASON_LABELS } from '@/lib/labels'

/** The printable record of an approved session, with signature lines. */
export function BeritaAcaraPage() {
  const opnameId = Number(useParams().opnameId)
  const path = { opname_id: opnameId }
  const opname = useQuery(opnamesReadOpnameOptions({ path }))
  const lines = useQuery(
    opnamesListLinesOptions({ path, query: { show: 'variance', limit: 2000 } }),
  )
  const back = (
    <BackLink to={`/stok-opname/${opnameId}`} label="Kembali ke opname" />
  )

  if (opname.isPending || lines.isPending) {
    return <p className="text-muted-foreground">Memuat…</p>
  }
  if (opname.isError || lines.isError) {
    return (
      <>
        {back}
        <p className="mt-4 text-destructive">
          {errorMessage(opname.error ?? lines.error)}
        </p>
      </>
    )
  }

  const document = <Report opname={opname.data} lines={lines.data.items} />
  return (
    <>
      {back}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Berita Acara</h1>
        <Button onClick={() => window.print()}>
          <PrinterIcon />
          Cetak
        </Button>
      </div>
      <div className="mt-6 overflow-x-auto rounded-xl border bg-white p-6 text-black shadow-sm">
        {document}
      </div>
      {createPortal(
        <div className="print-only">
          <style>{'@page { size: A4; margin: 15mm; }'}</style>
          {document}
        </div>,
        window.document.body,
      )}
    </>
  )
}

function Report({
  opname,
  lines,
}: {
  opname: OpnamePublic
  lines: OpnameLinePublic[]
}) {
  const kind = opname.is_opening ? 'Opname Awal' : 'Stok Opname'
  return (
    <article className="mx-auto max-w-[180mm] text-[10pt] leading-snug">
      <header className="text-center">
        <h2 className="text-[14pt] font-bold tracking-wide uppercase">
          Berita Acara {kind}
        </h2>
        <p className="tabular-nums">No. {opname.number}</p>
      </header>

      {opname.reversal && (
        <p className="mt-4 border border-black p-2 font-semibold">
          DIBATALKAN dengan {opname.reversal.number} oleh{' '}
          {opname.reversal.created_by_name},{' '}
          {formatDateTime(opname.reversal.created_at)}. Alasan:{' '}
          {opname.reversal.reason}
        </p>
      )}

      <dl className="mt-5 grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1">
        <dt>Lokasi</dt>
        <dd>{opname.location_name}</dd>
        <dt>Cakupan</dt>
        <dd>
          {opname.scope_label} ({opname.line_count} SKU)
        </dd>
        <dt>Dibuka</dt>
        <dd>
          {formatDateTime(opname.opened_at)} oleh {opname.opened_by_name}
        </dd>
        {opname.counting_closed_at && (
          <>
            <dt>Penghitungan ditutup</dt>
            <dd>
              {formatDateTime(opname.counting_closed_at)} oleh{' '}
              {opname.counting_closed_by_name}
            </dd>
          </>
        )}
        {opname.approved_at && (
          <>
            <dt>Disetujui</dt>
            <dd>
              {formatDateTime(opname.approved_at)} oleh{' '}
              {opname.approved_by_name}
            </dd>
          </>
        )}
        <dt>Checker</dt>
        <dd>{opname.checkers.map((c) => c.full_name).join(', ')}</dd>
      </dl>

      <p className="mt-4">
        {opname.is_opening
          ? `Stok awal ${opname.surplus_count ?? 0} SKU senilai ${money(opname.surplus_value ?? 0)}.`
          : `Selisih kurang ${opname.shortage_count ?? 0} SKU senilai ${money(opname.shortage_value ?? 0)}; selisih lebih ${opname.surplus_count ?? 0} SKU senilai ${money(opname.surplus_value ?? 0)}. SKU lain sesuai dengan stok sistem.`}
      </p>

      {lines.length > 0 && (
        <table className="mt-4 w-full border-collapse text-[9pt] [&_td]:border [&_td]:border-black [&_td]:px-1.5 [&_td]:py-1 [&_th]:border [&_th]:border-black [&_th]:px-1.5 [&_th]:py-1">
          <thead>
            <tr>
              <th className="w-8">No</th>
              <th className="text-left">Barang</th>
              <th className="text-right">Sistem</th>
              <th className="text-right">Fisik</th>
              <th className="text-right">Selisih</th>
              <th className="text-right">Nilai</th>
              {!opname.is_opening && <th className="text-left">Keterangan</th>}
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={line.id} className="break-inside-avoid">
                <td className="text-center tabular-nums">{index + 1}</td>
                <td>
                  {skuName(line)}
                  <span className="block text-[8pt] tabular-nums">
                    {[line.code, batchLabel(line)].filter(Boolean).join(' · ')}
                  </span>
                </td>
                <td className="text-right tabular-nums">
                  {quantity(line.system_quantity ?? 0)}
                </td>
                <td className="text-right tabular-nums">
                  {quantity(line.physical_quantity ?? 0)}
                </td>
                <td className="text-right tabular-nums">
                  {quantity(line.variance ?? 0)} {line.stock_unit}
                </td>
                <td className="text-right whitespace-nowrap tabular-nums">
                  {money(line.variance_value ?? 0)}
                </td>
                {!opname.is_opening && <td>{remark(line)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <section className="mt-10 grid grid-cols-3 gap-6 text-center break-inside-avoid">
        <Signature role="Dibuat oleh" name={opname.opened_by_name} />
        {opname.checkers.map((checker) => (
          <Signature key={checker.id} role="Checker" name={checker.full_name} />
        ))}
        <Signature role="Disetujui oleh" name={opname.approved_by_name} />
      </section>
    </article>
  )
}

function remark(line: OpnameLinePublic): string {
  if (Number(line.variance) > 0) return 'Lebih'
  const parts = [
    line.shortage_reason ? SHORTAGE_REASON_LABELS[line.shortage_reason] : '',
    line.resolution ? RESOLUTION_LABELS[line.resolution] : '',
  ]
  if (line.resolution === 'employee_charge' && line.charged_user_name) {
    const amount =
      line.charge_amount ?? Math.round(-Number(line.variance_value ?? 0))
    parts.push(`${line.charged_user_name} ${rupiah(amount)}`)
  }
  return parts.filter(Boolean).join(' · ')
}

function Signature({ role, name }: { role: string; name?: string | null }) {
  return (
    <div>
      <p>{role}</p>
      <div className="mt-16 border-b border-black" />
      <p className="mt-1">{name ?? ' '}</p>
    </div>
  )
}
