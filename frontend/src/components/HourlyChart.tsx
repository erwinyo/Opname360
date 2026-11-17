import { useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

import type { HourFigures } from '@/client'
import { money, rupiah } from '@/lib/format'
import { compact, hourRange } from '@/lib/reports'

// Follows the dataviz skill: thin bars with a 4px rounded end, a 2px gap
// between stacked parts, hairline grid, legend, hover and focus tooltips.
const TOP = 20
const PLOT = 190
const AXIS = 24
const LEFT = 52
const RIGHT = 8
const GAP = 2
const RADIUS = 4

const SERIES = [
  { key: 'cogs', label: 'HPP', color: 'var(--chart-2)' },
  { key: 'gross_profit', label: 'Laba kotor', color: 'var(--chart-1)' },
] as const

type Part = { color: string; from: number; to: number; end: boolean }

/** Per hour, a bar as tall as Net Sales: COGS below, gross profit on top.
 *  A negative part (more refunded than sold) hangs below the baseline. */
export function HourlyChart({ hours }: { hours: HourFigures[] }) {
  const box = useRef<HTMLDivElement>(null)
  const width = useWidth(box)
  const [active, setActive] = useState<number | null>(null)

  const stacks = hours.map((figures) => {
    let up = 0
    let down = 0
    const parts: Part[] = []
    for (const series of SERIES) {
      const value = Number(figures[series.key] ?? 0)
      if (value > 0) {
        parts.push({
          color: series.color,
          from: up,
          to: up + value,
          end: false,
        })
        up += value
      } else if (value < 0) {
        parts.push({
          color: series.color,
          from: down,
          to: down + value,
          end: false,
        })
        down += value
      }
    }
    // The outermost part each way gets the rounded data end.
    const last = (sign: number) =>
      parts.findLast((part) => Math.sign(part.to - part.from) === sign)
    for (const part of [last(1), last(-1)]) if (part) part.end = true
    return { figures, parts, up, down }
  })

  const max = Math.max(0, ...stacks.map((stack) => stack.up))
  const min = Math.min(0, ...stacks.map((stack) => stack.down))
  const step = niceStep((max - min) / 4 || 1)
  const top = Math.ceil(max / step) * step || step
  const bottom = Math.floor(min / step) * step
  const y = (value: number) => TOP + ((top - value) / (top - bottom)) * PLOT
  const ticks: number[] = []
  for (let tick = bottom; tick <= top + step / 2; tick += step) ticks.push(tick)

  const plotWidth = Math.max(0, width - LEFT - RIGHT)
  const band = hours.length ? plotWidth / hours.length : 0
  const barWidth = Math.min(24, band * 0.6)
  const every = band < 28 ? 2 : 1
  const peak = stacks.reduce<number | null>(
    (best, stack, i) =>
      stack.up > 0 && (best === null || stack.up > stacks[best].up) ? i : best,
    null,
  )
  const shown = active === null ? null : stacks[active].figures

  return (
    <div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
        {[...SERIES].reverse().map((series) => (
          <li key={series.key} className="flex items-center gap-1.5">
            <span
              className="size-2.5 rounded-[2px]"
              style={{ background: series.color }}
            />
            {series.label}
          </li>
        ))}
        <li>Tinggi batang = penjualan bersih</li>
      </ul>
      <div ref={box} className="relative mt-2">
        {width > 0 && (
          <svg
            width={width}
            height={TOP + PLOT + AXIS}
            role="img"
            aria-label="Penjualan bersih, HPP, dan laba kotor per jam"
            className="block"
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={LEFT}
                  x2={width - RIGHT}
                  y1={y(tick)}
                  y2={y(tick)}
                  stroke={tick === 0 ? 'oklch(0.82 0 0)' : 'var(--border)'}
                  strokeWidth={1}
                  shapeRendering="crispEdges"
                />
                <text
                  x={LEFT - 8}
                  y={y(tick)}
                  dy="0.32em"
                  textAnchor="end"
                  className="fill-muted-foreground text-[11px] tabular-nums"
                >
                  {compact(tick)}
                </text>
              </g>
            ))}
            {stacks.map((stack, i) => {
              const center = LEFT + band * (i + 0.5)
              const x = center - barWidth / 2
              return (
                <g key={stack.figures.hour}>
                  {active === i && (
                    <rect
                      x={center - band / 2}
                      y={TOP}
                      width={band}
                      height={PLOT}
                      className="fill-muted"
                    />
                  )}
                  {stack.parts.map((part, j) => {
                    const rising = part.to > part.from
                    // Parts after the first each way leave a 2px gap.
                    const gap = part.from === 0 ? 0 : GAP
                    const outer = y(part.to)
                    const inner = y(part.from) + (rising ? -gap : gap)
                    const height = Math.abs(inner - outer)
                    if (height < 0.5) return null
                    return (
                      <path
                        key={j}
                        d={barPath(
                          x,
                          Math.min(outer, inner),
                          barWidth,
                          height,
                          part.end ? (rising ? 'top' : 'bottom') : null,
                        )}
                        fill={part.color}
                      />
                    )
                  })}
                  {i === peak && (
                    <text
                      x={center}
                      y={y(stack.up) - 6}
                      textAnchor="middle"
                      className="fill-foreground text-[11px] font-medium"
                    >
                      {compact(stack.figures.net_sales)}
                    </text>
                  )}
                  {i % every === 0 && (
                    <text
                      x={center}
                      y={TOP + PLOT + 16}
                      textAnchor="middle"
                      className="fill-muted-foreground text-[11px] tabular-nums"
                    >
                      {String(stack.figures.hour).padStart(2, '0')}
                    </text>
                  )}
                  <rect
                    x={center - band / 2}
                    y={TOP}
                    width={band}
                    height={PLOT + AXIS}
                    fill="transparent"
                    tabIndex={0}
                    aria-label={`${hourRange(stack.figures.hour)}: penjualan bersih ${rupiah(stack.figures.net_sales)}`}
                    className="outline-none"
                    onPointerEnter={() => setActive(i)}
                    onPointerLeave={() => setActive(null)}
                    onFocus={() => setActive(i)}
                    onBlur={() => setActive(null)}
                  />
                </g>
              )
            })}
          </svg>
        )}
        {shown && active !== null && (
          <Tooltip
            figures={shown}
            left={Math.min(
              Math.max(LEFT + band * (active + 0.5), 104),
              width - 104,
            )}
          />
        )}
      </div>
    </div>
  )
}

function Tooltip({ figures, left }: { figures: HourFigures; left: number }) {
  return (
    <div
      className="pointer-events-none absolute top-0 w-52 -translate-x-1/2 rounded-lg border bg-popover px-3 py-2 text-sm shadow-md"
      style={{ left }}
    >
      <p className="text-xs text-muted-foreground">
        {hourRange(figures.hour)} · {figures.receipt_count} struk
      </p>
      <p className="mt-1 font-semibold">{rupiah(figures.net_sales)}</p>
      <p className="text-xs text-muted-foreground">Penjualan bersih</p>
      {[...SERIES].reverse().map((series) => (
        <p
          key={series.key}
          className="mt-1 flex items-center gap-2 whitespace-nowrap"
        >
          <span
            className="h-0.5 w-3 rounded-full"
            style={{ background: series.color }}
          />
          <span className="font-medium">{money(figures[series.key] ?? 0)}</span>
          <span className="text-xs text-muted-foreground">{series.label}</span>
        </p>
      ))}
    </div>
  )
}

/** 1, 2 or 5 times a power of ten, at least `raw`. */
function niceStep(raw: number): number {
  const power = 10 ** Math.floor(Math.log10(raw))
  const scaled = raw / power
  return (scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10) * power
}

/** A bar part, rounded at its data end only (square at the baseline). */
function barPath(
  x: number,
  top: number,
  width: number,
  height: number,
  round: 'top' | 'bottom' | null,
): string {
  const r = round ? Math.min(RADIUS, height, width / 2) : 0
  const right = x + width
  const bottom = top + height
  if (round === 'top') {
    return `M${x},${bottom}V${top + r}Q${x},${top} ${x + r},${top}H${right - r}Q${right},${top} ${right},${top + r}V${bottom}Z`
  }
  if (round === 'bottom') {
    return `M${x},${top}H${right}V${bottom - r}Q${right},${bottom} ${right - r},${bottom}H${x + r}Q${x},${bottom} ${x},${bottom - r}Z`
  }
  return `M${x},${top}H${right}V${bottom}H${x}Z`
}

function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return width
}
