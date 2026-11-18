import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** What prints on A4 instead of the screen, as on the Berita Acara. */
export function A4Print({ children }: { children: ReactNode }) {
  return createPortal(
    <div className="print-only text-black">
      <style>{'@page { size: A4; margin: 15mm; }'}</style>
      {children}
    </div>,
    document.body,
  )
}
