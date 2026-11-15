import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  activityLogListEntriesOptions,
  usersListUsersOptions,
} from '@/client/@tanstack/react-query.gen'
import { Pager } from '@/components/Pager'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { documentPath } from '@/lib/labels'

const PAGE_SIZE = 50
const EVERYONE = 'all'

export function ActivityLogPage() {
  const [userId, setUserId] = useState(EVERYONE)
  const [offset, setOffset] = useState(0)
  const users = useQuery(usersListUsersOptions())
  const log = useQuery({
    ...activityLogListEntriesOptions({
      query: {
        user_id: userId === EVERYONE ? undefined : Number(userId),
        offset,
        limit: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  })
  const total = log.data?.total ?? 0

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Log Aktivitas</h1>
      <p className="mt-1 text-muted-foreground">
        Siapa melakukan apa, dan kapan. Catatan ini tidak bisa diubah atau
        dihapus.
      </p>

      <div className="mt-6">
        <Select
          value={userId}
          onValueChange={(value) => {
            setUserId(value)
            setOffset(0)
          }}
        >
          <SelectTrigger className="bg-card" aria-label="Pengguna">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EVERYONE}>Semua pengguna</SelectItem>
            {users.data?.map((user) => (
              <SelectItem key={user.id} value={String(user.id)}>
                {user.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {log.isError && (
        <p className="mt-6 text-destructive">{errorMessage(log.error)}</p>
      )}
      {log.data && total === 0 && (
        <p className="mt-4 rounded-xl border border-dashed p-6 text-muted-foreground">
          Belum ada aktivitas.
        </p>
      )}
      {total > 0 && (
        <>
          <ol className="mt-4 rounded-xl border bg-card">
            {log.data?.items.map((entry) => {
              const path =
                entry.entity_type && entry.entity_id
                  ? documentPath(entry.entity_type, entry.entity_id)
                  : null
              return (
                <li
                  key={entry.id}
                  className="grid gap-1 border-b px-4 py-3 last:border-b-0 sm:grid-cols-[11rem_1fr]"
                >
                  <div className="text-sm text-muted-foreground">
                    <time dateTime={entry.created_at}>
                      {formatDateTime(entry.created_at)}
                    </time>
                    <span className="block font-medium text-foreground">
                      {entry.user_name ?? 'Sistem'}
                    </span>
                  </div>
                  <p>
                    {path ? (
                      <Link
                        to={path}
                        className="underline-offset-4 hover:underline"
                      >
                        {entry.summary}
                      </Link>
                    ) : (
                      entry.summary
                    )}
                  </p>
                </li>
              )
            })}
          </ol>
          <Pager
            offset={offset}
            pageSize={PAGE_SIZE}
            total={total}
            unit="catatan"
            onChange={setOffset}
          />
        </>
      )}
    </>
  )
}
