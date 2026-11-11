import { useEffect, useId, useState, type ReactNode } from 'react'

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Any = any

/** Минимальный набор иконок (inline SVG, наследуют currentColor). */
const PATHS: Record<string, ReactNode> = {
  layers: <><path d="M12 3 3 8l9 5 9-5-9-5Z" /><path d="m3 13 9 5 9-5" /><path d="m3 17.5 9 5 9-5" opacity=".5" /></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z" /><path d="M8 7h8M8 11h6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  file: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></>,
  upload: <><path d="M12 16V4m0 0-4 4m4-4 4 4" /><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></>,
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  back: <path d="M19 12H5m6-6-6 6 6 6" />,
  spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />,
  shield: <><path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />,
  download: <><path d="M12 4v12m0 0-4-4m4 4 4-4" /><path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" /></>,
  warn: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17h.01" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
}

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg className="ico" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{PATHS[name]}</svg>
  )
}

export function Card({ children, className = '', glow = false, as: Tag = 'div' }: { children: ReactNode; className?: string; glow?: boolean; as?: Any }) {
  return <Tag className={`card ${glow ? 'glow' : ''} ${className}`}>{children}</Tag>
}

export type Tone = 'ok' | 'warn' | 'bad' | 'info'
export function Badge({ tone = 'info', children, icon }: { tone?: Tone; children: ReactNode; icon?: string }) {
  return <span className={`badge ${tone}`}>{icon && <Icon name={icon} size={14} />}{children}</span>
}

/** Подсказка ⓘ: доступна с клавиатуры и экранных читалок. */
export function Hint({ text, label = 'Пояснение' }: { text: string; label?: string }) {
  const id = useId()
  return (
    <span className="hint">
      <button type="button" className="hint-btn" aria-label={label} aria-describedby={id}><Icon name="info" size={15} /></button>
      <span role="tooltip" id={id} className="hint-pop">{text}</span>
    </span>
  )
}

export function Details({ title, children, open = false }: { title: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details className="details" open={open}>
      <summary>{title}</summary>
      <div className="details-body">{children}</div>
    </details>
  )
}

export function Stat({ value, label, tone, hint }: { value: ReactNode; label: ReactNode; tone?: Tone; hint?: string }) {
  return (
    <div className={`stat ${tone ?? ''}`}>
      <div className="stat-v">{value}</div>
      <div className="stat-l">{label}{hint && <Hint text={hint} />}</div>
    </div>
  )
}

/** Главный вывод шага простым языком. */
export function Verdict({ title, children, badge }: { title: string; children: ReactNode; badge?: ReactNode }) {
  return (
    <Card glow className="verdict">
      <div className="verdict-head"><span className="eyebrow"><Icon name="spark" size={16} /> {title}</span>{badge}</div>
      <div className="verdict-body">{children}</div>
    </Card>
  )
}

export function StepHeader({ n, total, eyebrow, title, lead }: { n: number; total: number; eyebrow: string; title: ReactNode; lead: string }) {
  return (
    <header className="step-head">
      <span className="eyebrow">{eyebrow} {n} / {total}</span>
      <h1 className="h1">{title}</h1>
      <p className="lead">{lead}</p>
    </header>
  )
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="skel" aria-hidden="true">{Array.from({ length: lines }).map((_, i) => <i key={i} style={{ width: `${90 - i * 15}%` }} />)}</div>
}

/** Прогресс расчёта: сменяющиеся понятные сообщения. */
export function Progress({ messages }: { messages: string[] }) {
  const [i, setI] = useState(0)
  useEffect(() => { const h = setInterval(() => setI((x) => (x + 1) % messages.length), 2600); return () => clearInterval(h) }, [messages.length])
  return (
    <Card className="progress" glow>
      <div className="orb-mini" aria-hidden="true" />
      <div role="status" aria-live="polite"><b>{messages[i]}</b><div className="bar-ind"><i /></div></div>
    </Card>
  )
}

export const pct = (v: number) => `${(v * 100).toFixed(0)}%`
export const sg = (v: number, d = 1) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d).replace('.', ',')}`

/** Цвет ячейки тепловой карты: от розового (труднее) к фиолетово-синему/бирюзовому (легче). */
export function heatColor(v: number | null) {
  if (v == null) return 'transparent'
  const t = Math.max(0, Math.min(1, (v - 0.2) / 0.6))
  const h = 330 - t * 130            // 330 розовый → 200 бирюзовый
  return `hsl(${h} 70% ${34 + t * 8}% / ${0.55 + 0.3 * (1 - Math.abs(t - 0.5) * 0.6)})`
}
