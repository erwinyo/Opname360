import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** What the receipt printer prints: 80 mm paper, as long as it needs. */
export function ThermalPrint({ children }: { children: ReactNode }) {
  return createPortal(
    <div className="print-only">
      <style>{'@page { size: 80mm auto; margin: 0; }'}</style>
      <div className="w-[72mm] px-[4mm] py-[3mm] font-mono text-[9pt] leading-snug text-black">
        {children}
      </div>
    </div>,
    document.body,
  )
}

/** One line of a slip: what on the left, the amount on the right. */
export function SlipRow({
  label,
  value,
  bold,
}: {
  label: ReactNode
  value: ReactNode
  bold?: boolean
}) {
  return (
    <div
      className={
        bold ? 'flex justify-between font-bold' : 'flex justify-between'
      }
    >
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  )
}
