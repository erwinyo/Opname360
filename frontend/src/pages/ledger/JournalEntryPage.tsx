import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'

import {
  ledgerReadEntryOptions,
  ledgerReverseEntryMutation,
} from '@/client/@tanstack/react-query.gen'
import { BackLink, Facts } from '@/components/documents'
import { Field, FormDialog } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage, queryClient } from '@/lib/api'
import { formatDate, formatDateTime, money } from '@/lib/format'
import { ENTRY_SOURCE_LABELS, documentPath } from '@/lib/labels'

import { Amount } from './shared'

export function JournalEntryPage() {
  const entryId = Number(useParams().entryId)
  const entry = useQuery(
    ledgerReadEntryOptions({ path: { entry_id: entryId } }),
  )
  const [reversing, setReversing] = useState(false)

  if (entry.isPending) return <p className="text-muted-foreground">Memuat…</p>
  if (entry.isError) {
    return (
      <>
        <BackLink to="/jurnal" label="Jurnal" />
        <p className="mt-4 text-destructive">{errorMessage(entry.error)}</p>
      </>
    )
  }
  const data = entry.data
  const document =
    data.document_type && data.document_id
      ? documentPath(data.document_type, data.document_id)
      : null
  const reversible =
    data.source !== 'document' && !data.reverses_id && !data.reversed_by_id
  return (
    <>
      <BackLink to="/jurnal" label="Jurnal" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          Jurnal {data.number}
        </h1>
        {reversible && (
          <Button variant="outline" onClick={() => setReversing(true)}>
            Batalkan
          </Button>
        )}
      </div>
      <p className="mt-1 text-muted-foreground">{data.description}</p>
      <Facts
        facts={[
          ['Tanggal', formatDate(data.entry_date)],
          ['Sumber', ENTRY_SOURCE_LABELS[data.source]],
          [
            'Dokumen',
            document ? (
              <Link
                key="document"
                to={document}
                className="text-primary underline"
              >
                {data.document_number}
              </Link>
            ) : (
              (data.document_number ?? '—')
            ),
          ],
          [
            'Dicatat',
            `${formatDateTime(data.created_at)} oleh ${data.created_by_name ?? 'sistem'}`,
          ],
          ...(data.reverses_id
            ? ([
                [
                  'Membatalkan',
                  <Link
                    key="reverses"
                    to={`/jurnal/${data.reverses_id}`}
                    className="text-primary underline"
                  >
                    {data.reverses_number}
                  </Link>,
                ],
              ] as [string, React.ReactNode][])
            : []),
          ...(data.reversed_by_id
            ? ([
                [
                  'Dibatalkan oleh',
                  <Link
                    key="reversed-by"
                    to={`/jurnal/${data.reversed_by_id}`}
                    className="text-primary underline"
                  >
                    {data.reversed_by_number}
                  </Link>,
                ],
              ] as [string, React.ReactNode][])
            : []),
        ]}
      />
      <div className="mt-4 rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Akun</TableHead>
              <TableHead className="text-right">Debit</TableHead>
              <TableHead className="text-right">Kredit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell
                  className={Number(line.credit) > 0 ? 'pl-8' : undefined}
                >
                  <Link to={`/buku-besar?akun=${line.account_id}`}>
                    {line.account_code} {line.account_name}
                  </Link>
                  {(line.supplier_name ?? line.user_name) && (
                    <span className="block text-xs text-muted-foreground">
                      {line.supplier_name ?? line.user_name}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  <Amount value={line.debit} />
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  <Amount value={line.credit} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell className="font-semibold">Jumlah</TableCell>
              <TableCell className="text-right font-semibold whitespace-nowrap tabular-nums">
                {money(data.total)}
              </TableCell>
              <TableCell className="text-right font-semibold whitespace-nowrap tabular-nums">
                {money(data.total)}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>
      {reversing && (
        <ReverseDialog
          entryId={data.id}
          number={data.number}
          onClose={() => setReversing(false)}
        />
      )}
    </>
  )
}

function ReverseDialog({
  entryId,
  number,
  onClose,
}: {
  entryId: number
  number: string
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const reverse = useMutation({
    ...ledgerReverseEntryMutation(),
    onSuccess: (mirror) => {
      queryClient.invalidateQueries()
      toast.success(`Jurnal ${number} dibatalkan dengan ${mirror.number}.`)
      onClose()
    },
  })
  return (
    <FormDialog
      title={`Batalkan jurnal ${number}?`}
      description="Jurnal tidak dihapus: dibuat jurnal kebalikannya bertanggal hari ini."
      submitLabel="Batalkan jurnal"
      destructive
      pending={reverse.isPending}
      error={reverse.error}
      onSubmit={() =>
        reverse.mutate({ path: { entry_id: entryId }, body: { reason } })
      }
      onClose={onClose}
    >
      <Field id="reverse-reason" label="Alasan">
        <Textarea
          id="reverse-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={300}
          autoFocus
        />
      </Field>
    </FormDialog>
  )
}
