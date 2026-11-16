import { queryClient } from '@/lib/api'

/** Refetch everything cached about one session: header and lines. */
export function refreshOpname(opnameId: number) {
  return queryClient.invalidateQueries({
    predicate: (query) => {
      const key = query.queryKey[0] as { _id?: string; path?: object }
      return (
        typeof key === 'object' &&
        key?._id?.startsWith('opnames') === true &&
        JSON.stringify(key.path) === JSON.stringify({ opname_id: opnameId })
      )
    },
  })
}
