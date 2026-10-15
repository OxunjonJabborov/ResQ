import { Minus, Plus } from 'lucide-react'

export function QtyStepper({ value, max, onChange, disabled }: { value: number; max: number; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <div className="inline-flex items-center rounded-xl border border-line bg-card">
      <button type="button" className="p-2 text-muted disabled:opacity-40" disabled={disabled || value <= 1} onClick={() => onChange(value - 1)} aria-label="−">
        <Minus className="h-4 w-4" />
      </button>
      <span className="w-8 text-center text-sm font-semibold tabular-nums">{value}</span>
      <button type="button" className="p-2 text-muted disabled:opacity-40" disabled={disabled || value >= max} onClick={() => onChange(value + 1)} aria-label="+">
        <Plus className="h-4 w-4" />
      </button>
    </div>
  )
}
