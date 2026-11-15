import { Navigate, Route, Routes } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { Button } from '@/components/ui/button'
import { useMe } from '@/lib/auth'
import { CategoriesPage } from '@/pages/catalogue/CategoriesPage'
import { ProductFormPage } from '@/pages/catalogue/ProductFormPage'
import { ProductsPage } from '@/pages/catalogue/ProductsPage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { GoodsReceiptPage } from '@/pages/purchasing/GoodsReceiptPage'
import { GoodsReceiptsPage } from '@/pages/purchasing/GoodsReceiptsPage'
import { SuppliersPage } from '@/pages/purchasing/SuppliersPage'
import { StockCardPage } from '@/pages/stock/StockCardPage'
import { StockPage } from '@/pages/stock/StockPage'
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
        {user.role !== 'cashier' && (
          <>
            <Route path="produk" element={<ProductsPage />} />
            <Route path="produk/baru" element={<ProductFormPage />} />
            <Route path="produk/:productId" element={<ProductFormPage />} />
            <Route path="kategori" element={<CategoriesPage />} />
            <Route path="stok" element={<StockPage />} />
            <Route path="stok/:skuId" element={<StockCardPage />} />
            <Route path="barang-masuk" element={<GoodsReceiptsPage />} />
            <Route path="barang-masuk/baru" element={<GoodsReceiptPage />} />
            <Route
              path="barang-masuk/:receiptId"
              element={<GoodsReceiptPage />}
            />
            <Route path="pemasok" element={<SuppliersPage />} />
          </>
        )}
        {user.role === 'owner' && (
          <Route path="pengguna" element={<UsersPage me={user} />} />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
