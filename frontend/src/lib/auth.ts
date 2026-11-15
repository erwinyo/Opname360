import { useQuery } from '@tanstack/react-query'

import { authReadMe } from '@/client'
import type { Role } from '@/client'
import { meQueryKey } from '@/lib/api'

export const ROLE_LABELS: Record<Role, string> = {
  owner: 'Pemilik',
  admin: 'Admin',
  cashier: 'Kasir',
}

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  owner: 'Semua menu, termasuk pengguna dan persetujuan',
  admin: 'Katalog, barang masuk, stok, dan pembukuan',
  cashier: 'Penjualan di kasir',
}

/** The signed-in user, or `null` when nobody is signed in. */
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async () => {
      const { data, response } = await authReadMe()
      if (data) return data
      // No response at all means the server couldn't be reached.
      if (response?.status === 401) return null
      throw new Error('Could not load the signed-in user')
    },
    retry: false,
  })
}
