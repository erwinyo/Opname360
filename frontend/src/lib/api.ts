import { QueryClient } from '@tanstack/react-query'

import type { UserPublic } from '@/client'
import { client } from '@/client/client.gen'

export const queryClient = new QueryClient()

export const meQueryKey = ['me'] as const

/**
 * Switch who is signed in (`null`: nobody) and forget everything fetched for
 * the previous user, so the next person on this device never sees it.
 */
export function setSignedInUser(user: UserPublic | null) {
  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== meQueryKey[0],
  })
  queryClient.setQueryData(meQueryKey, user)
}

// A 401 on anything but sign-in means the session is gone (12 idle hours, or
// the Owner deactivated the account): show the sign-in screen at once.
client.interceptors.response.use((response, request) => {
  if (response.status === 401 && !request.url.endsWith('/auth/login')) {
    setSignedInUser(null)
  }
  return response
})

/** The message to show for a failed API call. Business errors arrive in Indonesian. */
export function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const { detail } = error
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return 'Periksa kembali isian Anda.'
  }
  return 'Terjadi kesalahan. Coba lagi.'
}
