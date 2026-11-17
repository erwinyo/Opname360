import { useEffect, useRef } from 'react'

/** Calls `onChange` whenever the server records something new (rule 8).
 *  The browser reconnects by itself if the stream drops. */
export function useLiveUpdates(onChange: () => void) {
  const latest = useRef(onChange)
  useEffect(() => {
    latest.current = onChange
  })
  useEffect(() => {
    const source = new EventSource('/api/v1/reports/live')
    let seen: string | null = null
    source.addEventListener('changed', (event) => {
      // The first message after (re)connecting only says where we are.
      if (seen !== null && event.data !== seen) latest.current()
      seen = event.data
    })
    return () => source.close()
  }, [])
}
