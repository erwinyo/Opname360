import JsBarcode from 'jsbarcode'
import { useEffect, useRef } from 'react'

/** A Code 128 barcode that stretches to fill its box, with its digits below. */
export function Barcode({ value }: { value: string }) {
  const svg = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const element = svg.current
    if (!element) return
    JsBarcode(element, value, {
      format: 'CODE128',
      width: 2,
      height: 60,
      margin: 0,
      fontSize: 18,
      textMargin: 2,
    })
    // Scale with CSS instead of the pixel size JsBarcode sets.
    const width = element.getAttribute('width')
    const height = element.getAttribute('height')
    element.setAttribute('viewBox', `0 0 ${parseFloat(width ?? '0')} ${parseFloat(height ?? '0')}`)
    element.removeAttribute('width')
    element.removeAttribute('height')
    element.setAttribute('preserveAspectRatio', 'none')
  }, [value])

  return <svg ref={svg} className="block h-full w-full" aria-label={value} />
}
