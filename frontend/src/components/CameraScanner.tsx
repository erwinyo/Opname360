import { useEffect, useRef, useState } from 'react'

import { BarcodeDetector } from '@/lib/camera'

const FORMATS = ['code_128', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_39']
// A label held in view is read again and again; it counts once until it has
// been out of sight this long.
const GONE_AFTER_MS = 1000

/** The back camera as a scanner. Calls `onScan` once per label shown. */
export function CameraScanner({ onScan }: { onScan: (code: string) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const latest = useRef(onScan)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    latest.current = onScan
  }, [onScan])

  useEffect(() => {
    if (!BarcodeDetector) return
    const detector = new BarcodeDetector({ formats: FORMATS })
    let stream: MediaStream | null = null
    let stopped = false
    let lastCode = ''
    let lastSeen = 0

    const look = async () => {
      if (stopped) return
      const element = video.current
      if (element && element.readyState >= 2) {
        const found = await detector.detect(element).catch(() => [])
        const code = found[0]?.rawValue
        const now = Date.now()
        if (code) {
          if (code !== lastCode || now - lastSeen > GONE_AFTER_MS) {
            navigator.vibrate?.(60)
            latest.current(code)
          }
          lastCode = code
          lastSeen = now
        }
      }
      setTimeout(look, 200)
    }

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((media) => {
        stream = media
        if (stopped || !video.current) {
          media.getTracks().forEach((track) => track.stop())
          return
        }
        video.current.srcObject = media
        void video.current.play()
        void look()
      })
      .catch(() =>
        setError('Kamera tidak bisa dibuka. Izinkan akses kamera di browser.'),
      )
    return () => {
      stopped = true
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  if (error) return <p className="text-sm text-destructive">{error}</p>
  return (
    <video
      ref={video}
      muted
      playsInline
      aria-label="Kamera untuk scan barcode"
      className="aspect-[4/3] w-full rounded-xl bg-black object-cover"
    />
  )
}
