import { formatMoney } from '../lib/format'

export function Price({ current, original, size = 'md' }: { current: number; original?: number; size?: 'sm' | 'md' | 'lg' }) {
  const big = { sm: 'text-base', md: 'text-lg', lg: 'text-2xl' }[size]
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <span className={`${big} font-bold text-ink`}>{formatMoney(current)}</span>
      {original !== undefined && original > current && (
        <span className="text-sm text-muted line-through">{formatMoney(original)}</span>
      )}
    </div>
  )
}

export function DiscountBadge({ percent, className = '' }: { percent: number; className?: string }) {
  if (!percent) return null
  return (
    <span className={`rounded-lg bg-deal-600 px-2 py-0.5 text-xs font-bold text-white ${className}`}>−{percent}%</span>
  )
}
