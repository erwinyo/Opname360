import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { PlusIcon, SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { EntrySource } from '@/client'
import { ledgerListEntriesOptions } from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import { DateInput, Empty, Filters } from '@/components/reports'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate, money, today } from '@/lib/format'
import { ENTRY_SOURCE_LABELS } from '@/lib/labels'
import { ALL } from '@/lib/reports'

const PAGE_SIZE = 50

/** Every journal entry, newest first. */
export function JournalPage() {
  const navigate = useNavigate()
  const [start, setStart] = useState(() => `${today().slice(0, 8)}01`)
  const [end, setEnd] = useState(today)
  const [source, setSource] = useState(ALL)
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(typed.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [typed])
  const entries = useQuery({
    ...ledgerListEntriesOptions({
      query: {
        start,
        end,
        source: source === ALL ? undefined : (source as EntrySource),
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jurnal</h1>
          <p className="mt-1 text-muted-foreground">
            Semua jurnal, yang otomatis dari dokumen maupun yang diketik.
          </p>
        </div>
        <Button asChild>
          <Link to="/jurnal/baru">
            <PlusIcon />
            Jurnal umum
          </Link>
        </Button>
      </div>
      <Filters>
        <DateInput label="Dari tanggal" value={start} onChange={setStart} />
        <span className="text-muted-foreground">s.d.</span>
        <DateInput label="Sampai tanggal" value={end} onChange={setEnd} />
        <Select value={source} onValueChange={setSource}>
          <SelectTrigger className="bg-card" aria-label="Sumber">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Semua sumber</SelectItem>
            {(Object.keys(ENTRY_SOURCE_LABELS) as EntrySource[]).map((key) => (
              <SelectItem key={key} value={key}>
                {ENTRY_SOURCE_LABELS[key]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative min-w-48 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Cari nomor atau keterangan"
            aria-label="Cari jurnal"
            className="bg-card pl-8"
          />
        </div>
      </Filters>
      {entries.isError && (
        <p className="mt-6 text-destructive">{errorMessage(entries.error)}</p>
      )}
      {entries.data && entries.data.total === 0 && (
        <Empty>Belum ada jurnal dalam periode ini.</Empty>
      )}
      {entries.data && entries.data.total > 0 && (
        <>
          <div className="mt-4 rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Jurnal</TableHead>
                  <TableHead className="hidden md:table-cell">
                    Keterangan
                  </TableHead>
                  <TableHead className="text-right">Jumlah</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.data.items.map((entry) => (
                  <TableRow
                    key={entry.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/jurnal/${entry.id}`)}
                  >
                    <TableCell>
                      <Link
                        to={`/jurnal/${entry.id}`}
                        className="font-medium tabular-nums"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {entry.number}
                      </Link>
                      <span className="block text-xs text-muted-foreground">
                        {formatDate(entry.entry_date)}
                        {entry.document_number && ` · ${entry.document_number}`}
                      </span>
                      <span className="block text-sm md:hidden">
                        {entry.description}
                      </span>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {entry.description}
                      {entry.reversed_by_number && (
                        <span className="block text-xs text-muted-foreground">
                          Dibatalkan oleh {entry.reversed_by_number}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap tabular-nums">
                      {money(entry.total)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={entries.data.total}
            unit="jurnal"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
