import { Navigate, Route, Routes } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { Button } from '@/components/ui/button'
import { useMe } from '@/lib/auth'
import { CategoriesPage } from '@/pages/catalogue/CategoriesPage'
import { ImportPage } from '@/pages/catalogue/ImportPage'
import { ProductFormPage } from '@/pages/catalogue/ProductFormPage'
import { ProductsPage } from '@/pages/catalogue/ProductsPage'
import { HomePage } from '@/pages/HomePage'
import { ActivityLogPage } from '@/pages/ActivityLogPage'
import { LabelsPage } from '@/pages/labels/LabelsPage'
import { LoginPage } from '@/pages/LoginPage'
import { BeritaAcaraPage } from '@/pages/opname/BeritaAcaraPage'
import { CountingPage } from '@/pages/opname/CountingPage'
import { CountPage } from '@/pages/opname/CountPage'
import { EmployeeChargesPage } from '@/pages/opname/EmployeeChargesPage'
import { OpenOpnamePage } from '@/pages/opname/OpenOpnamePage'
import { OpnamePage } from '@/pages/opname/OpnamePage'
import { OpnamesPage } from '@/pages/opname/OpnamesPage'
import { CloseShiftPage } from '@/pages/pos/CloseShiftPage'
import { ReceiptPage } from '@/pages/pos/ReceiptPage'
import { ShiftPage } from '@/pages/pos/ShiftPage'
import { ShiftsPage } from '@/pages/pos/ShiftsPage'
import { TillPage } from '@/pages/pos/TillPage'
import { PromotionFormPage } from '@/pages/promotions/PromotionFormPage'
import { PromotionsPage } from '@/pages/promotions/PromotionsPage'
import { ProductionReceiptPage } from '@/pages/production/ProductionReceiptPage'
import { ProductionReceiptsPage } from '@/pages/production/ProductionReceiptsPage'
import { GoodsReceiptPage } from '@/pages/purchasing/GoodsReceiptPage'
import { GoodsReceiptsPage } from '@/pages/purchasing/GoodsReceiptsPage'
import { SupplierReturnPage } from '@/pages/purchasing/SupplierReturnPage'
import { SupplierReturnsPage } from '@/pages/purchasing/SupplierReturnsPage'
import { SuppliersPage } from '@/pages/purchasing/SuppliersPage'
import { DailyStockPage } from '@/pages/reports/DailyStockPage'
import { PaymentMethodsPage } from '@/pages/settings/PaymentMethodsPage'
import { ShopSettingsPage } from '@/pages/settings/ShopSettingsPage'
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
        <Route path="hitung" element={<CountingPage />} />
        <Route path="hitung/:opnameId" element={<CountPage />} />
        <Route path="shift/:shiftId" element={<ShiftPage user={user} />} />
        <Route path="struk/:receiptId" element={<ReceiptPage user={user} />} />
        {user.role !== 'admin' && (
          <>
            <Route path="kasir" element={<TillPage screen="sale" />} />
            <Route path="kasir/retur" element={<TillPage screen="return" />} />
            <Route
              path="kasir/transaksi"
              element={<TillPage screen="transactions" />}
            />
            <Route path="kasir/tutup" element={<CloseShiftPage />} />
          </>
        )}
        {user.role !== 'cashier' && (
          <>
            <Route path="produk" element={<ProductsPage />} />
            <Route path="produk/baru" element={<ProductFormPage />} />
            <Route path="produk/impor" element={<ImportPage />} />
            <Route path="label" element={<LabelsPage />} />
            <Route path="produk/:productId" element={<ProductFormPage />} />
            <Route path="kategori" element={<CategoriesPage />} />
            <Route path="stok" element={<StockPage />} />
            <Route path="stok/:skuId" element={<StockCardPage />} />
            <Route path="stok-opname" element={<OpnamesPage />} />
            <Route path="stok-opname/baru" element={<OpenOpnamePage />} />
            <Route path="stok-opname/:opnameId" element={<OpnamePage />} />
            <Route
              path="stok-opname/:opnameId/berita-acara"
              element={<BeritaAcaraPage />}
            />
            <Route path="barang-masuk" element={<GoodsReceiptsPage />} />
            <Route path="barang-masuk/baru" element={<GoodsReceiptPage />} />
            <Route
              path="barang-masuk/:receiptId"
              element={<GoodsReceiptPage />}
            />
            <Route path="hasil-produksi" element={<ProductionReceiptsPage />} />
            <Route
              path="hasil-produksi/baru"
              element={<ProductionReceiptPage />}
            />
            <Route
              path="hasil-produksi/:receiptId"
              element={<ProductionReceiptPage />}
            />
            <Route path="retur-pembelian" element={<SupplierReturnsPage />} />
            <Route
              path="retur-pembelian/baru"
              element={<SupplierReturnPage />}
            />
            <Route
              path="retur-pembelian/:returnId"
              element={<SupplierReturnPage />}
            />
            <Route path="pemasok" element={<SuppliersPage />} />
            <Route path="shift" element={<ShiftsPage />} />
            <Route path="promo" element={<PromotionsPage />} />
            <Route path="promo/baru" element={<PromotionFormPage />} />
            <Route path="promo/:promotionId" element={<PromotionFormPage />} />
            <Route path="laporan/stok-harian" element={<DailyStockPage />} />
          </>
        )}
        {user.role === 'owner' && (
          <>
            <Route path="pengguna" element={<UsersPage me={user} />} />
            <Route path="log-aktivitas" element={<ActivityLogPage />} />
            <Route path="ganti-rugi" element={<EmployeeChargesPage />} />
            <Route path="pengaturan-toko" element={<ShopSettingsPage />} />
            <Route path="metode-pembayaran" element={<PaymentMethodsPage />} />
          </>
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
