import type { DocumentStatus, MovementReason, PaymentStatus } from '@/client'

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
}

/** Where a Stock Movement's document can be opened, if it has a screen. */
export function documentPath(type: string, id: number): string | null {
  if (type === 'goods_receipt') return `/barang-masuk/${id}`
  return null
}
