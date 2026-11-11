import { useEffect, useMemo, useState } from 'react'
import { T, type Lang } from './i18n'
import './index.css'

const API = '/api'
/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = any

async function j(url: string, init?: RequestInit) {
  const r = await fetch(API + url, init)
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail ?? msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}

const pct = (v: number) => (v * 100).toFixed(0) + '%'
function heatColor(v: number | null) {
  if (v == null) return 'transparent'
  const t = Math.max(0, Math.min(1, (v - 0.2) / 0.6)) // 0.2..0.8
  const h = 10 + t * 120 // красный → зелёный
  return `hsl(${h} 65% ${88 - t * 18}%)`
}

export default function App() {
  const [lang, setLang] = useState<Lang>('ru')
  const t = T[lang]
  const [tab, setTab] = useState(0)
  const [id, setId] = useState<string | null>(null)
  const [quality, setQuality] = useState<Any>(null)
  const [synthetic, setSynthetic] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [diff, setDiff] = useState<Any>(null)
  const [tb, setTb] = useState<Any>(null)
  const [hours, setHours] = useState<Any>(null)
  const [dif, setDif] = useState<Any>(null)

  const analyze = async (rid: string) => {
    setBusy(true); setErr(''); setDiff(null); setTb(null); setHours(null); setDif(null)
    try {
      const [d, b, h, df] = await Promise.all([
        j(`/analyze/difficulty?id=${rid}`), j(`/analyze/textbooks?id=${rid}`),
        j(`/optimize/hours?id=${rid}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
        j(`/analyze/dif?id=${rid}`),
      ])
      setDiff(d); setTb(b); setHours(h); setDif(df)
      return true
    } catch (e: Any) { setErr(String(e.message ?? e)); return false } finally { setBusy(false) }
  }
  const load = async (p: Promise<Any>) => {
    setBusy(true); setErr('')
    try {
      const r = await p
      setId(r.id); setQuality(r.quality); setSynthetic(r.synthetic)
      if (await analyze(r.id)) setTab(1)
    } catch (e: Any) { setErr(String(e.message ?? e)); setBusy(false) }
  }
  const demo = (n: string) => load(j(`/demo/${n}`, { method: 'POST' }))
  const upload = (files: FileList | null) => {
    if (!files?.length) return
    const fd = new FormData()
    Array.from(files).forEach((f) => fd.append('files', f))
    load(j('/import', { method: 'POST', body: fd }))
  }

  return (
    <div className="app">
      {synthetic && <div className="banner">{t.synth}</div>}
      <header>
        <h1>{t.app}</h1>
        <div className="lang">
          {(['ru', 'kz'] as Lang[]).map((l) => (
            <button key={l} className={l === lang ? 'on' : ''} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
          ))}
        </div>
      </header>
      <nav>
        {t.tabs.map((x, i) => (
          <button key={i} className={i === tab ? 'on' : ''} onClick={() => setTab(i)}>{x}</button>
        ))}
      </nav>
      {lang === 'kz' && <div className="note small">{t.ruNote}</div>}
      {busy && <div className="note busy">{t.loading}</div>}
      {err && <pre className="error">{err}</pre>}
      <main>
        {tab === 0 && <DataTab t={t} demo={demo} upload={upload} quality={quality} busy={busy} id={id} reanalyze={analyze} />}
        {tab > 0 && tab < 5 && !id && <p className="note">{t.pick}</p>}
        {tab === 1 && diff && <DifficultyTab t={t} d={diff} dif={dif} />}
        {tab === 2 && tb && <TextbooksTab t={t} d={tb} id={id!} />}
        {tab === 3 && hours && <HoursTab t={t} d={hours} id={id!} />}
        {tab === 4 && id && <ReportTab t={t} id={id} lang={lang} />}
        {tab === 4 && !id && <p className="note">{t.pick}</p>}
        {tab === 5 && <ValidationTab t={t} />}
      </main>
    </div>
  )
}

function DataTab({ t, demo, upload, quality, busy, id, reanalyze }: Any) {
  return (
    <section>
      <div className="row">
        <button className="primary" disabled={busy} onClick={() => demo('main')}>{t.loadDemo}</button>
        <button disabled={busy} onClick={() => demo('small')}>{t.loadSmall}</button>
      </div>
      <p className="muted">{t.or}</p>
      <input type="file" multiple accept=".csv,.xlsx,.xls" onChange={(e) => upload(e.target.files)} disabled={busy} />
      <p className="muted small">{t.uploadHint} <a href={`${API}/templates`}>{t.templates}</a></p>
      {id && <Settings t={t} id={id} reanalyze={reanalyze} busy={busy} />}
      {quality && (
        <div className="card">
          <h3>{t.quality}</h3>
          {quality.errors.length > 0 && <><h4>{t.errors}</h4><ul className="bad">{quality.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul></>}
          <h4>{t.warnings}</h4>
          {quality.warnings.length ? <ul className="warn">{quality.warnings.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul> : <p className="muted">{t.noWarn}</p>}
          <h4>{t.stats}</h4>
          <div className="stats">
            {Object.entries(quality.stats).filter(([k]) => k !== 'context').map(([k, v]) => <div key={k}><b>{String(v)}</b><span>{k}</span></div>)}
          </div>
        </div>
      )}
    </section>
  )
}

function DifficultyTab({ t, d, dif }: Any) {
  const [showSchools, setShowSchools] = useState(false)
  const top = d.topics.slice(0, 3)
  const hm = d.heatmap_textbook
  const hs = d.heatmap_school
  return (
    <section>
      <h2>{t.hardTitle}</h2>
      <div className="cards">
        {top.map((x: Any) => (
          <div className="card" key={x.topic}>
            <b>#{x.rank} {x.topic}</b>
            <div className="big">{x.difficulty.toFixed(2)}</div>
            <div className="muted small">{t.interval}: [{x.ci[0].toFixed(2)}; {x.ci[1].toFixed(2)}]</div>
            <div className="muted small">IRT b = {x.difficulty_irt.toFixed(2)} [{x.irt_ci[0].toFixed(2)}; {x.irt_ci[1].toFixed(2)}]</div>
            {x.flagged_items > 0 && <div className="warn small">{x.flagged_items} {t.flagged}</div>}
          </div>
        ))}
      </div>
      <p className="muted small">{d.method}</p>
      {d.link_warning && <p className="warn">{d.link_warning}</p>}
      {d.irt_warning && <p className="warn">{d.irt_warning}</p>}
      <ItemsTable t={t} items={d.items} />
      {dif?.available && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{t.difTitle}: {dif.n_flagged} / {dif.n_items}</h3>
          {dif.flagged.length === 0 ? <p className="muted">{t.difNone}</p> : (
            <table><tbody>{dif.flagged.map((f: Any) => <tr key={f.task_id}><td>{f.task_id}</td><td>{f.topic}</td><td>Δb = {f.delta_b.toFixed(2)}</td></tr>)}</tbody></table>
          )}
          <p className="muted small">{dif.note}</p>
        </div>
      )}
      {hm && (
        <>
          <h3>{t.heat}</h3>
          <table className="heat">
            <thead><tr><th></th>{hm.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{hm.rows.map((r: Any) => (
              <tr key={r.topic}><td className="lbl">{r.topic}</td>{r.values.map((v: number | null, i: number) => <td key={i} style={{ background: heatColor(v) }}>{v == null ? '' : pct(v)}</td>)}</tr>
            ))}</tbody>
          </table>
        </>
      )}
      <h3>{t.difficulty}</h3>
      <table>
        <tbody>{d.topics.map((x: Any) => (
          <tr key={x.topic}><td>{x.rank}</td><td>{x.topic}</td>
            <td style={{ width: '40%' }}><div className="bar"><i style={{ width: `${x.difficulty * 100}%` }} /><u style={{ left: `${x.ci[0] * 100}%`, width: `${(x.ci[1] - x.ci[0]) * 100}%` }} /></div></td>
            <td>{x.difficulty.toFixed(2)}</td><td className="muted">{x.difficulty_irt.toFixed(2)}</td></tr>
        ))}</tbody>
      </table>
      <button onClick={() => setShowSchools(!showSchools)}>{t.heatSchool}</button>
      {showSchools && (
        <div className="scroll"><table className="heat">
          <thead><tr><th></th>{hs.columns.map((c: string) => <th key={c} title={c}>{c.slice(0, 8)}</th>)}</tr></thead>
          <tbody>{hs.rows.map((r: Any) => (
            <tr key={r.school}><td className="lbl">{r.school}</td>{r.values.map((v: number | null, i: number) => <td key={i} style={{ background: heatColor(v) }}>{v == null ? '' : pct(v)}</td>)}</tr>
          ))}</tbody>
        </table></div>
      )}
    </section>
  )
}

function Forest({ rows, lo, hi }: { rows: Any[]; lo: number; hi: number }) {
  const W = 560, rowH = 44
  const x = (v: number) => 120 + ((v - lo) / (hi - lo)) * (W - 140)
  return (
    <svg viewBox={`0 0 ${W} ${rows.length * rowH + 30}`} width="100%" className="forest">
      <line x1={x(0)} x2={x(0)} y1={0} y2={rows.length * rowH + 6} stroke="#888" strokeDasharray="3 3" />
      {rows.map((r, i) => (
        <g key={i} transform={`translate(0 ${i * rowH + 22})`}>
          <text x={0} y={4} fontSize="12">{r.label}</text>
          {r.naive != null && <circle cx={x(r.naive)} cy={-8} r={5} fill="#c0392b"><title>naive {r.naive.toFixed(1)}</title></circle>}
          {r.insufficient ? <text x={x(0) + 8} y={10} fontSize="11" fill="#b9770e">—</text> : (
            <>
              <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={10} y2={10} stroke="#1f5fbf" strokeWidth={3} />
              <circle cx={x(r.est)} cy={10} r={5} fill="#1f5fbf"><title>{r.est.toFixed(1)}</title></circle>
            </>
          )}
        </g>
      ))}
      {[lo, 0, hi].map((v) => <text key={v} x={x(v)} y={rows.length * rowH + 22} fontSize="10" textAnchor="middle">{v}</text>)}
    </svg>
  )
}

function TextbooksTab({ t, d, id }: Any) {
  const [why, setWhy] = useState<Any>(null)
  if (!d.available) return <p className="note">{d.reason}</p>
  const rows = d.comparisons.map((c: Any) => ({ label: `${c.textbook} ${t.ppvs} ${c.vs}`, naive: c.naive_diff, est: c.estimate, ci: c.ci, insufficient: c.status === 'insufficient' }))
  const all = rows.flatMap((r: Any) => [r.naive, r.ci[0], r.ci[1]])
  const lo = Math.floor(Math.min(-2, ...all) - 1), hi = Math.ceil(Math.max(2, ...all) + 1)
  return (
    <section>
      <h2>{t.tbTitle}</h2>
      <div className="legend"><span className="dot red" /> {t.naive} &nbsp; <span className="dot blue" /> {t.adj}</div>
      <Forest rows={rows} lo={lo} hi={hi} />
      <table>
        <thead><tr><th></th><th>{t.schools}</th><th>{t.naive}</th><th>{t.adj}</th><th></th></tr></thead>
        <tbody>{d.comparisons.map((c: Any) => (
          <tr key={c.textbook}>
            <td><b>{c.textbook}</b> {t.ppvs} {c.vs}</td><td>{c.schools}/{c.schools_ref}</td>
            <td className="red">{c.naive_diff >= 0 ? '+' : ''}{c.naive_diff.toFixed(1)}</td>
            <td>{c.status === 'insufficient' ? <span className="badge warn">{t.insufficient}</span> : <>{c.estimate.toFixed(1)} [{c.ci[0].toFixed(1)}; {c.ci[1].toFixed(1)}]</>}
              {c.status === 'tentative' && <div className="warn small">{c.status_text}</div>}
              {c.robust && c.status !== 'insufficient' && <div className={'small ' + (c.robust_agrees ? 'muted' : 'warn')}>{t.robust}: {c.robust.estimate.toFixed(1)} [{c.robust.ci[0].toFixed(1)}; {c.robust.ci[1].toFixed(1)}] {c.robust_agrees ? '✓' : '⚠'}</div>}</td>
            <td><button onClick={async () => setWhy(await j(`/why/textbook?id=${id}&textbook=${c.textbook}`))}>{t.why}</button></td>
          </tr>
        ))}</tbody>
      </table>
      <p className="muted small">{t.caveat}</p>
      {d.simpson && (
        <>
          <h3>{t.simpson}</h3>
          <table><thead><tr><th></th>{d.simpson.columns.map((c: string) => <th key={c}>{c}</th>)}<th>{t.schools}</th></tr></thead>
            <tbody>{d.simpson.rows.map((r: Any) => (
              <tr key={r.school_type}><td>{r.school_type}</td>{r.means.map((m: number | null, i: number) => <td key={i}>{m == null ? '' : (m).toFixed(1)}</td>)}<td>{r.schools.join(' / ')}</td></tr>
            ))}</tbody></table>
        </>
      )}
      <h3>{t.topicEff}</h3>
      <p className="muted small">{t.topicEffNote}</p>
      <table>
        <thead><tr><th></th><th>{t.topic}</th><th>{t.devCol}</th><th>{t.diffCol}</th><th></th></tr></thead>
        <tbody>{d.topic_effects.slice(0, 8).map((e: Any, i: number) => (
          <tr key={i} className={e.significant_dev ? 'hl' : ''}><td>{e.textbook}</td><td>{e.topic}</td>
            <td><b>{e.deviation >= 0 ? '+' : ''}{e.deviation.toFixed(1)}</b> [{e.dev_ci[0].toFixed(1)}; {e.dev_ci[1].toFixed(1)}]</td>
            <td className="muted">{e.estimate >= 0 ? '+' : ''}{e.estimate.toFixed(1)}</td>
            <td>{e.gated ? <span className="badge warn">{t.insufficient}</span> : e.significant_dev ? '✓' : ''}</td></tr>
        ))}</tbody>
      </table>
      <p className="muted small">{d.method}</p>
      {why && <Why t={t} w={why} close={() => setWhy(null)} />}
    </section>
  )
}

function Why({ t, w, close }: Any) {
  return (
    <div className="modal" onClick={close}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <h3>{w.headline ?? w.error}</h3>
        {w.data && <p><b>{t.data}:</b> {w.data}</p>}
        {w.evidence && <p><b>{t.evidence}:</b> {w.evidence}</p>}
        {w.method && <p><b>{t.method}:</b> {w.method}</p>}
        {w.uncertainty && <p><b>{t.uncertainty}:</b> {w.uncertainty}</p>}
        {w.limits && <><b>{t.limits}:</b><ul>{w.limits.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></>}
        {w.scope && <p className="muted small">{w.scope}</p>}
        <button onClick={close}>{t.close}</button>
      </div>
    </div>
  )
}

function HoursTab({ t, d, id }: Any) {
  const [plan, setPlan] = useState<Record<string, number>>({})
  const [fc, setFc] = useState<Any>(null)
  const [why, setWhy] = useState<Any>(null)
  const cur = useMemo(() => Object.fromEntries((d.rows ?? []).map((r: Any) => [r.topic, r.current])), [d])
  const rec = useMemo(() => Object.fromEntries((d.rows ?? []).map((r: Any) => [r.topic, r.recommended])), [d])
  useEffect(() => { setPlan(cur) }, [cur])
  const total = Object.values(plan).reduce((a, b) => a + b, 0)
  useEffect(() => {
    if (!d.available || !Object.keys(plan).length) return
    if (total !== d.total) { setFc({ error: `${t.sum}: ${total} ≠ ${d.total}` }); return }
    const h = setTimeout(async () => {
      try { setFc(await j(`/optimize/scenario?id=${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan }) })) } catch (e: Any) { setFc({ error: e.message }) }
    }, 250)
    return () => clearTimeout(h)
  }, [plan, total, d, id, t.sum])
  if (!d.available) return <p className="note">{d.reason}</p>
  return (
    <section>
      <h2>{t.hoursTitle}</h2>
      <p className="muted">{d.recommendation_text}</p>
      <div className="row">
        <button className="primary" onClick={() => setPlan(rec)}>{t.applyRec}</button>
        <button onClick={() => setPlan(cur)}>{t.reset}</button>
        <b className={total === d.total ? '' : 'bad'}>{t.sum}: {total} / {d.total}</b>
      </div>
      <table>
        <thead><tr><th></th><th>{t.cur}</th><th>{t.plan}</th><th></th><th>{t.rec}</th><th>{t.range}</th><th></th></tr></thead>
        <tbody>{d.rows.map((r: Any) => {
          const v = plan[r.topic] ?? r.current
          const oob = v < r.min || v > r.max
          return (
            <tr key={r.topic} className={oob ? 'oob' : ''}>
              <td>{r.topic}</td><td>{r.current}</td>
              <td style={{ minWidth: 160 }}><input type="range" min={1} max={r.max + 3} value={v} onChange={(e) => setPlan({ ...plan, [r.topic]: +e.target.value })} /> <b>{v}</b>{oob && <div className="warn small">{t.bounds} [{r.min}–{r.max}]</div>}</td>
              <td className={r.delta > 0 ? 'up' : r.delta < 0 ? 'down' : ''}>{r.delta > 0 ? '+' : ''}{r.delta || ''}</td>
              <td><b>{r.recommended}</b></td><td>{r.range[0]}–{r.range[1]}</td>
              <td><button onClick={async () => setWhy(await j(`/why/hours?id=${id}&topic=${encodeURIComponent(r.topic)}`))}>{t.why}</button></td>
            </tr>
          )
        })}</tbody>
      </table>
      <div className="card">
        <h3>{t.forecast}</h3>
        {fc?.error ? <p className="bad">{fc.error}</p> : fc && (
          <div className="big">{fc.gain_pp >= 0 ? '+' : ''}{fc.gain_pp.toFixed(2)} <span className="muted small">[{fc.gain_ci[0].toFixed(2)}; {fc.gain_ci[1].toFixed(2)}]</span></div>
        )}
        <p className="muted small">{d.gain_note}</p>
      </div>
      <ul className="muted small">{d.assumptions.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul>
      {why && <Why t={t} w={why} close={() => setWhy(null)} />}
    </section>
  )
}

function ReportTab({ t, id, lang }: Any) {
  const [rl, setRl] = useState<Lang>(lang)
  const [llm, setLlm] = useState(false)
  const link = (fmt: string) => `${API}/report?id=${id}&lang=${rl}&fmt=${fmt}&llm=${llm}`
  return (
    <section>
      <h2>{t.reportTitle}</h2>
      <div className="row">
        <label>{t.lang}: <select value={rl} onChange={(e) => setRl(e.target.value as Lang)}><option value="ru">Русский</option><option value="kz">Қазақша</option></select></label>
        <label><input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} /> {t.llm}</label>
      </div>
      <div className="row">
        <a className="btn primary" href={link('docx')}>{t.download} DOCX</a>
        <a className="btn" href={link('pdf')}>{t.download} PDF</a>
      </div>
      {rl === 'kz' && <p className="warn">{t.kzNote}</p>}
    </section>
  )
}

function ValidationTab({ t }: Any) {
  const [v, setV] = useState<Any>(null)
  useEffect(() => { j('/validation').then(setV).catch(() => setV({})) }, [])
  if (!v) return <p className="note">…</p>
  const tb = v.textbooks
  const hr: Any[] = v.hours ?? []
  const variants = Array.from(new Set(hr.map((r) => r.variant)))
  const mean = (a: number[]) => a.reduce((x, y) => x + y, 0) / (a.length || 1)
  return (
    <section>
      <h2>{t.valTitle}</h2>
      <p className="muted">{t.valIntro}</p>
      {tb && (
        <div className="cards">
          <div className="card"><div className="big">{tb.ci_coverage}/{tb.n_seeds}</div><div className="muted small">{t.valCover}</div></div>
          <div className="card"><div className="big">{tb.robust_coverage}/{tb.n_seeds}</div><div className="muted small">{t.valRobust}</div></div>
          <div className="card"><div className="big red">{tb.naive_wrong}/{tb.n_seeds}</div><div className="muted small">{t.valNaive}</div></div>
          <div className="card"><div className="big">{tb.rho_irt_mean.toFixed(2)}</div><div className="muted small">{t.valRho}: IRT (min {tb.rho_irt_min.toFixed(2)}) · {tb.rho_classic_mean.toFixed(2)} (min {tb.rho_classic_min.toFixed(2)})</div></div>
        </div>
      )}
      <p className="warn small">{t.valNaiveNote}</p>
      {hr.length > 0 && (
        <>
          <h3>{t.valHours}</h3>
          <table>
            <thead><tr><th></th><th>tilt 0</th><th>tilt 0.5</th><th>tilt 1.0</th></tr></thead>
            <tbody>{variants.map((vn) => (
              <tr key={String(vn)}><td>{String(vn)}</td>{[0, 0.5, 1].map((tl) => {
                const rows = hr.filter((r) => r.variant === vn && r.tilt === tl)
                const g = mean(rows.map((r) => r.gain_true_pp))
                return <td key={tl} className={g < 0 ? 'down' : ''}>{g >= 0 ? '+' : ''}{g.toFixed(3)} п.п. ({t.valBest} +{mean(rows.map((r) => r.optimum_true_pp)).toFixed(3)})</td>
              })}</tr>
            ))}</tbody>
          </table>
          <p className="muted small">{t.valHoursNote}</p>
        </>
      )}
      {!tb && !hr.length && <p className="note">{t.valNone}</p>}
    </section>
  )
}

function ItemsTable({ t, items }: Any) {
  const [all, setAll] = useState(false)
  const rows = (all ? items : items.filter((x: Any) => x.flagged)).slice(0, all ? 200 : 50)
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t.itemsTitle} <button onClick={() => setAll(!all)}>{all ? t.itemsFlagged : t.itemsAll}</button></h3>
      {rows.length === 0 ? <p className="muted">{t.itemsNone}</p> : (
        <div className="scroll"><table>
          <thead><tr><th>task</th><th>{t.topic}</th><th>p</th><th>r_it</th><th>IRT a</th><th>IRT b</th><th></th></tr></thead>
          <tbody>{rows.map((x: Any) => (
            <tr key={x.task_id} className={x.flagged ? 'oob' : ''}><td>{x.task_id}</td><td>{x.topic}</td><td>{x.p_correct?.toFixed(2)}</td>
              <td>{x.discrimination == null ? '—' : x.discrimination.toFixed(2)}</td><td>{x.irt_a?.toFixed(2)}</td><td>{x.irt_b?.toFixed(2)}</td><td className="warn small">{x.flags}</td></tr>
          ))}</tbody>
        </table></div>
      )}
    </div>
  )
}

function Settings({ t, id, reanalyze, busy }: Any) {
  const [cfg, setCfg] = useState<Any>(null)
  const [draft, setDraft] = useState<Any>({})
  const [msg, setMsg] = useState('')
  useEffect(() => { j(`/config?id=${id}`).then((r) => { setCfg(r); setDraft(r.config) }) }, [id])
  if (!cfg) return null
  const keys = Object.keys(cfg.editable)
  const apply = async () => {
    const body: Any = {}
    keys.forEach((k) => { if (draft[k] !== cfg.config[k]) body[k] = Number(draft[k]) })
    if (!Object.keys(body).length) return
    try {
      const r = await j(`/config?id=${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      setCfg({ ...cfg, config: r.config }); setMsg(''); await reanalyze(id)
    } catch (e: Any) { setMsg(String(e.message ?? e)) }
  }
  return (
    <details className="card">
      <summary>{t.settings}</summary>
      <p className="muted small">{t.settingsNote}</p>
      <div className="grid2">
        {keys.map((k) => (
          <label key={k} className="small">{k} <input type="number" step="any" min={cfg.editable[k][0]} max={cfg.editable[k][1]} value={draft[k] ?? ''} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} /></label>
        ))}
      </div>
      {msg && <p className="bad">{msg}</p>}
      <button className="primary" disabled={busy} onClick={apply}>{t.applySettings}</button>
    </details>
  )
}
