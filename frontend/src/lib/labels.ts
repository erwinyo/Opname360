import type {
  AccountType,
  DocumentStatus,
  EntrySource,
  MovementReason,
  OpnameScope,
  OpnameStatus,
  PaymentStatus,
  PromotionStatus,
  ReceiptKind,
  Resolution,
  ShortageReason,
  TargetKind,
} from '@/client'

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  draft: 'Draf',
  completed: 'Selesai',
  reversed: 'Dibatalkan',
}

export const PAYMENT_LABELS: Record<PaymentStatus, string> = {
  paid: 'Lunas',
  owed: 'Hutang',
}

export const REASON_LABELS: Record<MovementReason, string> = {
  goods_receipt: 'Barang masuk',
  production_receipt: 'Hasil produksi',
  supplier_return: 'Retur pembelian',
  reversal: 'Pembatalan',
  cost_adjustment: 'Penyesuaian nilai',
  opname: 'Stok opname',
  opening: 'Stok awal',
  sale: 'Penjualan',
  customer_return: 'Retur penjualan',
  write_off: 'Dihapus (rusak)',
}

export const OPNAME_STATUS_LABELS: Record<OpnameStatus, string> = {
  counting: 'Penghitungan',
  review: 'Peninjauan',
  approved: 'Disetujui',
  cancelled: 'Dibatalkan',
  reversed: 'Dibatalkan setelah disetujui',
}

export const SCOPE_LABELS: Record<OpnameScope, string> = {
  everything: 'Semua SKU',
  categories: 'Kategori',
  sub_categories: 'Sub-kategori',
  skus: 'SKU pilihan',
}

export const SHORTAGE_REASON_LABELS: Record<ShortageReason, string> = {
  damaged: 'Rusak',
  lost: 'Hilang',
  miscounted: 'Salah hitung',
  unknown: 'Tidak diketahui',
  expired: 'Kedaluwarsa',
}

export const RESOLUTION_LABELS: Record<Resolution, string> = {
  company_loss: 'Kerugian perusahaan',
  employee_charge: 'Ganti rugi karyawan',
}

export const PROMOTION_STATUS_LABELS: Record<PromotionStatus, string> = {
  running: 'Berjalan',
  upcoming: 'Akan datang',
  ended: 'Selesai',
}

export const TARGET_KIND_LABELS: Record<TargetKind, string> = {
  categories: 'Kategori',
  sub_categories: 'Sub-kategori',
  products: 'Produk',
  skus: 'SKU',
}

export const RECEIPT_KIND_LABELS: Record<ReceiptKind, string> = {
  sale: 'Penjualan',
  return: 'Retur',
  exchange: 'Tukar tambah',
}

/** Where a Stock Movement's document can be opened, if it has a screen. */
export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  asset: 'Aset',
  liability: 'Kewajiban',
  equity: 'Ekuitas',
  revenue: 'Pendapatan',
  cogs: 'Harga pokok',
  expense: 'Beban',
}

export const ENTRY_SOURCE_LABELS: Record<EntrySource, string> = {
  document: 'Otomatis dari dokumen',
  manual: 'Jurnal umum',
  opening: 'Saldo awal',
}

export function documentPath(type: string, id: number): string | null {
  if (type === 'goods_receipt') return `/barang-masuk/${id}`
  if (type === 'production_receipt') return `/hasil-produksi/${id}`
  if (type === 'supplier_return') return `/retur-pembelian/${id}`
  if (type === 'stock_opname') return `/stok-opname/${id}`
  if (type === 'receipt') return `/struk/${id}`
  if (type === 'shift') return `/shift/${id}`
  if (type === 'cash_out') return '/kas-keluar'
  if (type === 'cash_transfer') return '/pindah-kas'
  if (type === 'supplier_payment') return '/bayar-hutang'
  if (type === 'employee_charge') return '/ganti-rugi'
  return null
}
