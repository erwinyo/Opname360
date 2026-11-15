import { Navigate, Route, Routes } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { Button } from '@/components/ui/button'
import { useMe } from '@/lib/auth'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { UsersPage } from '@/pages/users/UsersPage'

export function App() {
  const me = useMe()

  if (me.isPending) return null
  if (me.isError) {
    return (
      <main className="grid min-h-svh place-items-center px-4 text-center">
        <div>
          <p className="font-medium">Tidak bisa terhubung ke server.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Periksa koneksi internet Anda.
          </p>
          <Button className="mt-4" onClick={() => me.refetch()}>
            Coba lagi
          </Button>
        </div>
      </main>
    )
  }
  if (!me.data) return <LoginPage />

  const user = me.data
  return (
    <Routes>
      <Route element={<AppLayout user={user} />}>
        <Route index element={<HomePage user={user} />} />
        {user.role === 'owner' && (
          <Route path="pengguna" element={<UsersPage me={user} />} />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
