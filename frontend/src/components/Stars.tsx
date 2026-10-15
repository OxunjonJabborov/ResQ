import { Star } from 'lucide-react'

export function Stars({ value, size = 'h-4 w-4' }: { value: number; size?: string }) {
  return (
    <span className="inline-flex" aria-label={`${value.toFixed(1)} / 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={`${size} ${i <= Math.round(value) ? 'fill-amber-400 text-amber-400' : 'text-line'}`} aria-hidden />
      ))}
    </span>
  )
}

export function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" role="radiogroup">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          role="radio"
          aria-checked={value === i}
          aria-label={`${i}`}
          onClick={() => onChange(i)}
          className="rounded p-0.5"
        >
          <Star className={`h-8 w-8 ${i <= value ? 'fill-amber-400 text-amber-400' : 'text-line'}`} />
        </button>
      ))}
    </div>
  )
}
