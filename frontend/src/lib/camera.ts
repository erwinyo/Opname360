// The browser's own barcode reader: Chrome on Android has it, iPhone Safari
// doesn't yet.
// ponytail: native BarcodeDetector only; add a JS decoder if iPhones count.
type Detector = {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>
}
type DetectorClass = new (options?: { formats?: string[] }) => Detector

export const BarcodeDetector = (
  globalThis as { BarcodeDetector?: DetectorClass }
).BarcodeDetector

/** Whether this phone can scan with its camera. */
export const cameraScanning =
  BarcodeDetector !== undefined && !!navigator.mediaDevices?.getUserMedia
