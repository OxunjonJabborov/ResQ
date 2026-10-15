import { CheckCircle2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

type Toast = { id: number; message: string; tone: 'success' | 'error' }
let nextId = 1
const subscribers = new Set<(t: Toast) => void>()

// eslint-disable-next-line react-refresh/only-export-components
export function toast(message: string, tone: Toast['tone'] = 'success') {
  const item = { id: nextId++, message, tone }
  subscribers.forEach((fn) => fn(item))
}

export function ToastHost() {
  const [items, setItems] = useState<Toast[]>([])
  useEffect(() => {
    const add = (item: Toast) => {
      setItems((prev) => [...prev.slice(-2), item])
      setTimeout(() => setItems((prev) => prev.filter((p) => p.id !== item.id)), 3500)
    }
    subscribers.add(add)
    return () => {
      subscribers.delete(add)
    }
  }, [])
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6" aria-live="polite">
      {items.map((item) => (
        <div
          key={item.id}
          className={`pointer-events-auto flex max-w-md items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg ${
            item.tone === 'success' ? 'bg-ink' : 'bg-red-600'
          }`}
        >
          {item.tone === 'success' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {item.message}
        </div>
      ))}
    </div>
  )
}
