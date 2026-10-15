import { useEffect, useRef, useState } from 'react'

import { formatDate, formatMoney } from '../lib/format'

interface Point {
  date: string
  revenue: number
  orders: number
}

const BAR = '#059669' // brand-600, validated against the card surface
const GRID = '#e3e6e3'
const HEIGHT = 200
const PAD = { top: 12, right: 8, bottom: 24, left: 44 }

function compact(n: number): string {
  if (n >= 1_000_000) return `${+(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${+(n / 1_000).toFixed(0)}K`
  return String(n)
}

function niceMax(v: number): number {
  if (v <= 0) return 1
  const mag = 10 ** Math.floor(Math.log10(v))
  const step = [1, 2, 2.5, 5, 10].find((s) => s * mag >= v / 4)! * mag
  return Math.ceil(v / step) * step
}

/** Column path: 4px rounded data-end, square at the baseline. */
function columnPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, w / 2, h)
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}

/** Single-series daily revenue columns with a per-column hover/focus tooltip. */
export function RevenueChart({ data, label, ordersLabel }: { data: Point[]; label: string; ordersLabel: string }) {
  const wrap = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const max = niceMax(Math.max(...data.map((d) => d.revenue), 0))
  const plotW = width - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const band = plotW / data.length
  const barW = Math.min(24, Math.max(2, band - 2)) // 2px surface gap between touching bars
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max)
  const labelEvery = Math.ceil(data.length / Math.max(2, Math.floor(plotW / 56)))
  const active = hover !== null ? data[hover] : null

  return (
    <div ref={wrap} className="relative">
      <svg width={width} height={HEIGHT} role="img" aria-label={label} className="block" onMouseLeave={() => setHover(null)}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} stroke={GRID} strokeWidth={1} />
            <text x={PAD.left - 6} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="fill-muted text-[10px]">
              {compact(tick)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = PAD.left + i * band + (band - barW) / 2
          const h = Math.max(0, PAD.top + plotH - y(d.revenue))
          return (
            <g key={d.date}>
              {h > 0 && <path d={columnPath(x, y(d.revenue), barW, h)} fill={BAR} opacity={hover === null || hover === i ? 1 : 0.45} />}
              {i % labelEvery === 0 && (
                <text x={PAD.left + i * band + band / 2} y={HEIGHT - 6} textAnchor="middle" className="fill-muted text-[10px]">
                  {formatDate(d.date)}
                </text>
              )}
              {/* Hit target: the full band, taller than the mark. */}
              <rect
                x={PAD.left + i * band}
                y={PAD.top}
                width={band}
                height={plotH}
                fill="transparent"
                tabIndex={0}
                aria-label={`${formatDate(d.date)}: ${formatMoney(d.revenue)}`}
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
              />
            </g>
          )
        })}
      </svg>
      {active && hover !== null && (
        <div
          className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-line bg-card px-2.5 py-1.5 text-xs shadow-md"
          style={{ left: Math.min(Math.max(PAD.left + hover * band + band / 2, 70), width - 70) }}
        >
          <p className="font-medium text-muted">{formatDate(active.date)}</p>
          <p className="font-semibold text-ink">{formatMoney(active.revenue)}</p>
          <p className="text-muted">
            {ordersLabel}: {active.orders}
          </p>
        </div>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.date}>
              <th scope="row">{d.date}</th>
              <td>{d.revenue}</td>
              <td>{d.orders}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
