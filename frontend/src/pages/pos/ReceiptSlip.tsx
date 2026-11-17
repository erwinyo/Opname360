import type { ReceiptPublic, ShopSettingsPublic } from '@/client'
import { SlipRow } from '@/components/ThermalPrint'
import { formatDateTime, quantity, rupiah, skuName } from '@/lib/format'
import { Barcode } from '@/pages/labels/Barcode'

const KIND_TITLES = {
  sale: null,
  return: 'RETUR PENJUALAN',
  exchange: 'TUKAR TAMBAH',
} as const

function Rule() {
  return <div className="my-1.5 border-t border-dashed border-black" />
}

/** The printed Receipt: 80 mm, the number as a barcode (rule 10). */
export function ReceiptSlip({
  receipt,
  shop,
}: {
  receipt: ReceiptPublic
  shop?: ShopSettingsPublic
}) {
  const title = KIND_TITLES[receipt.kind]
  const cashGiven = receipt.payments.find((payment) => payment.is_cash)
  return (
    <>
      {shop && (
        <header className="text-center">
          <p className="text-[11pt] font-bold">{shop.name}</p>
          {shop.address && (
            <p className="whitespace-pre-line">{shop.address}</p>
          )}
        </header>
      )}
      {receipt.print_count > 1 && (
        <p className="mt-1 border border-black text-center font-bold">
          SALINAN
        </p>
      )}
      {receipt.status === 'voided' && (
        <p className="mt-1 border border-black text-center font-bold">
          DIBATALKAN
        </p>
      )}
      <Rule />
      {title && <p className="text-center font-bold">{title}</p>}
      <SlipRow label="No." value={receipt.number} />
      <SlipRow label="Tanggal" value={formatDateTime(receipt.created_at)} />
      <SlipRow label="Kasir" value={receipt.cashier_name} />
      {receipt.original_receipt_number && (
        <SlipRow label="Struk asal" value={receipt.original_receipt_number} />
      )}
      <Rule />
      {receipt.lines.map((line) => (
        <div key={line.id} className="mb-1">
          <p>
            {Number(line.quantity) < 0 && 'RETUR '}
            {skuName(line)}
          </p>
          <SlipRow
            label={`  ${quantity(Math.abs(Number(line.quantity)))} x ${rupiah(line.unit_price)}`}
            value={rupiah(line.line_total + line.discount)}
          />
          {line.discount !== 0 && (
            <SlipRow
              label={`  ${line.promotion_name ?? 'Diskon'}`}
              value={rupiah(-line.discount)}
            />
          )}
        </div>
      ))}
      <Rule />
      {receipt.discount_total > 0 && (
        <>
          <SlipRow label="Subtotal" value={rupiah(receipt.subtotal)} />
          <SlipRow label="Diskon" value={rupiah(-receipt.discount_total)} />
        </>
      )}
      {receipt.refund_total > 0 && (
        <SlipRow label="Retur" value={rupiah(-receipt.refund_total)} />
      )}
      <SlipRow
        label={receipt.total < 0 ? 'DIKEMBALIKAN' : 'TOTAL'}
        value={rupiah(Math.abs(receipt.total))}
        bold
      />
      {receipt.payments.map((payment, index) => (
        <SlipRow
          key={index}
          label={payment.method_name}
          value={rupiah(
            Math.abs(payment.amount) +
              (payment === cashGiven ? receipt.change_given : 0),
          )}
        />
      ))}
      {receipt.change_given > 0 && (
        <SlipRow label="Kembali" value={rupiah(receipt.change_given)} />
      )}
      <Rule />
      <div className="mx-auto mt-2 h-[12mm] w-[56mm]">
        <Barcode value={receipt.number} />
      </div>
      {shop?.receipt_footer && (
        <p className="mt-2 text-center whitespace-pre-line">
          {shop.receipt_footer}
        </p>
      )}
    </>
  )
}
