import { useCallback, useState } from 'react'

export interface Coords {
  lat: number
  lng: number
}

const KEY = 'resq.coords'

function readCached(): Coords | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Coords) : null
  } catch {
    return null
  }
}

/** Browser geolocation with a per-session cache; nothing is requested until `request()`. */
export function useGeolocation() {
  const [coords, setCoords] = useState<Coords | null>(readCached)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const request = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setError('unsupported')
      return
    }
    setLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const value = { lat: +pos.coords.latitude.toFixed(5), lng: +pos.coords.longitude.toFixed(5) }
        setCoords(value)
        setError(null)
        setLoading(false)
        try {
          sessionStorage.setItem(KEY, JSON.stringify(value))
        } catch {
          /* ignore */
        }
      },
      (err) => {
        setError(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable')
        setLoading(false)
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    )
  }, [])

  return { coords, error, loading, request }
}
