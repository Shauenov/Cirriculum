import { useEffect, useMemo, useState } from 'react'
import { API, j, post } from './api'
import type { T as TT } from './i18n'
import { Badge, Card, Details, heatColor, Hint, Icon, pct, sg, Stat, Verdict, type Any } from './ui'

type Tr = (typeof TT)['ru']
const f1 = (v: number, d = 1) => v.toFixed(d).replace('.', ',')

/* ---------- Шаг 1. Данные ---------- */
export function StepData({ t, quality, id, reanalyze, busy }: { t: Tr; quality: Any; id: string; reanalyze: (id: string) => void; busy: boolean }) {
  const hasErr = quality.errors.length > 0, hasWarn = quality.warnings.length > 0
  const tone = hasErr ? 'bad' : hasWarn ? 'warn' : 'ok'
  const ctx = quality.stats.context ?? {}
  return (
    <div className="stack">
      <Verdict title={t.whatWeSee} badge={<Badge tone={tone} icon={hasErr ? 'warn' : 'check'}>{hasErr ? t.qBad : hasWarn ? t.qWarn : t.qOk}</Badge>}>
        <div className="grid g4">
          {(['schools', 'students', 'tasks', 'topics', 'rows'] as const).map((k) => (
            <Stat key={k} value={Number(quality.stats[k === 'rows' ? 'rows_used' : k]).toLocaleString('ru-RU')} label={t.qStats[k]} />
          ))}
        </div>
      </Verdict>
      <div className="grid g2">
        <Card>
          <h3 className="h3">{t.warnings}</h3>
          {hasErr && <ul>{quality.errors.map((e: string, i: number) => <li key={i} style={{ color: 'var(--bad)' }}>{e}</li>)}</ul>}
          {hasWarn ? <ul className="muted">{quality.warnings.map((e: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{e}</li>)}</ul>
            : <p className="muted"><Icon name="check" size={16} /> {t.noWarn}</p>}
        </Card>
        <Card>
          <h3 className="h3">{t.ctxTitle}</h3>
          <div className="grid" style={{ gap: 8 }}>
            {Object.keys(t.ctxNames).map((k) => (
              <div className="row" key={k} style={{ justifyContent: 'space-between' }}>
                <span>{t.ctxNames[k]}</span><Badge tone={ctx[k] ? 'ok' : 'warn'}>{ctx[k] ? t.ctxHave : t.ctxNo}</Badge>
              </div>
            ))}
          </div>
          <p className="faint small">{t.ctxMissing}</p>
        </Card>
      </div>
      <Settings t={t} id={id} reanalyze={reanalyze} busy={busy} />
    </div>
  )
}

function Settings({ t, id, reanalyze, busy }: { t: Tr; id: string; reanalyze: (id: string) => void; busy: boolean }) {
  const [cfg, setCfg] = useState<Any>(null)
  const [draft, setDraft] = useState<Any>({})
  const [msg, setMsg] = useState('')
  useEffect(() => { j(`/config?id=${id}`).then((r) => { setCfg(r); setDraft(r.config) }).catch(() => undefined) }, [id])
  if (!cfg) return null
  const keys = Object.keys(cfg.editable)
  const apply = async () => {
    const body: Any = {}
    keys.forEach((k) => { if (Number(draft[k]) !== cfg.config[k]) body[k] = Number(draft[k]) })
    if (!Object.keys(body).length) return
    try {
      const r = await post(`/config?id=${id}`, body)
      setCfg({ ...cfg, config: r.config }); setMsg(''); reanalyze(id)
    } catch (e: Any) { setMsg(String(e.message ?? e)) }
  }
  return (
    <Details title={t.settings}>
      <p>{t.settingsNote}</p>
      <div className="grid g3">
        {keys.map((k) => (
          <label key={k} className="field">{k}
            <input type="number" step="any" min={cfg.editable[k][0]} max={cfg.editable[k][1]} value={draft[k] ?? ''} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} />
          </label>
        ))}
      </div>
      {msg && <p style={{ color: 'var(--bad)' }}>{msg}</p>}
      <button className="btn primary sm" disabled={busy} onClick={apply}>{t.applySettings}</button>
    </Details>
  )
}

/* ---------- Шаг 2. Темы ---------- */
export function StepTopics({ t, d, dif }: { t: Tr; d: Any; dif: Any }) {
  const [schools, setSchools] = useState(false)
  const [allItems, setAllItems] = useState(false)
  const top = d.topics.slice(0, 3)
  const names = top.map((x: Any) => x.topic).join(', ')
  const avgSolved = top.reduce((s: number, x: Any) => s + (1 - x.difficulty), 0) / (top.length || 1)
  const hm = d.heatmap_textbook, hs = d.heatmap_school
  const items = (allItems ? d.items : d.items.filter((x: Any) => x.flagged)).slice(0, 60)
  return (
    <div className="stack">
      <Verdict title={t.whatWeSee}>
        <p>{t.v2(names, pct(avgSolved))}</p>
        <p className="muted" style={{ fontSize: 15 }}>{t.v2b}</p>
      </Verdict>

      <div className="grid g3">
        {top.map((x: Any) => (
          <Card key={x.topic} className="topic-card">
            <span className="rank">{x.rank}</span>
            <h3 className="h3">{x.topic}</h3>
            <div className="stat-l">{t.topicHard}: <b style={{ color: 'var(--fg)' }}>{pct(1 - x.difficulty)}</b>
              <Hint text={t.hHard} />
            </div>
            <div className="diffbar" aria-hidden="true"><i style={{ width: `${x.difficulty * 100}%` }} /><u style={{ left: `${x.ci[0] * 100}%`, width: `${Math.max((x.ci[1] - x.ci[0]) * 100, 1)}%` }} /></div>
            {x.flagged_items > 0 && <Badge tone="warn" icon="warn">{x.flagged_items} {t.itemsTitle.toLowerCase()}</Badge>}
          </Card>
        ))}
      </div>

      {hm && (
        <Card>
          <h2 className="h2">{t.heatTitle}</h2>
          <p className="muted small">{t.heatLead}</p>
          <div className="legend"><span>{t.legendHard}</span><i className="ramp" /><span>{t.legendEasy}</span></div>
          <div className="tbl-wrap"><table className="heat">
            <thead><tr><th>{t.topicCol}</th>{hm.columns.map((c: string) => <th key={c} style={{ textAlign: 'center' }}>{c}</th>)}</tr></thead>
            <tbody>{hm.rows.map((r: Any) => (
              <tr key={r.topic}><td className="lbl">{r.topic}</td>{r.values.map((v: number | null, i: number) => <td key={i} style={{ background: heatColor(v) }}>{v == null ? '' : pct(v)}</td>)}</tr>
            ))}</tbody>
          </table></div>
        </Card>
      )}

      <Card>
        <h2 className="h2">{t.rankTitle}</h2>
        <div className="tbl-wrap"><table>
          <thead><tr><th>#</th><th>{t.topicCol}</th><th>{t.topicHard}</th><th style={{ width: '30%' }} /></tr></thead>
          <tbody>{d.topics.map((x: Any) => (
            <tr key={x.topic}><td>{x.rank}</td><td>{x.topic}</td><td>{pct(1 - x.difficulty)}</td>
              <td><div className="diffbar" aria-hidden="true"><i style={{ width: `${x.difficulty * 100}%` }} /><u style={{ left: `${x.ci[0] * 100}%`, width: `${Math.max((x.ci[1] - x.ci[0]) * 100, 1)}%` }} /></div></td></tr>
          ))}</tbody>
        </table></div>
      </Card>

      <div className="grid g2">
        <Card>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3 className="h3" style={{ margin: 0 }}>{t.itemsTitle}</h3>
            <button className="btn sm" onClick={() => setAllItems(!allItems)}>{allItems ? t.itemsFlagged : t.itemsAll}</button>
          </div>
          {items.length === 0 ? <p className="muted"><Icon name="check" size={16} /> {t.itemsNone}</p> : (
            <div className="tbl-wrap" style={{ maxHeight: 320, overflow: 'auto', marginTop: 10 }}><table>
              <thead><tr><th>№</th><th>{t.topicCol}</th><th>%</th><th>r</th><th /></tr></thead>
              <tbody>{items.map((x: Any) => (
                <tr key={x.task_id} className={x.flagged ? 'hl' : ''}><td>{x.task_id}</td><td>{x.topic}</td><td>{pct(x.p_correct)}</td>
                  <td>{x.discrimination == null ? '—' : f1(x.discrimination, 2)}</td><td className="faint small">{x.flags}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <Card>
          <div className="row"><h3 className="h3" style={{ margin: 0 }}>{t.difTitle}</h3><Hint text={t.hDIF} /></div>
          {dif?.available ? (
            dif.n_flagged === 0
              ? <p className="muted"><Icon name="check" size={16} /> {t.difNone}</p>
              : <><Badge tone="warn" icon="warn">{dif.n_flagged} {t.difSome}</Badge>
                <ul className="muted small">{dif.flagged.map((x: Any) => <li key={x.task_id}>{x.task_id} — {x.topic}</li>)}</ul></>
          ) : <p className="muted">{dif?.reason}</p>}
        </Card>
      </div>
      {d.link_warning && <Card className="err"><Icon name="warn" size={16} /> {d.link_warning}</Card>}
      {d.irt_warning && <Card className="err"><Icon name="warn" size={16} /> {d.irt_warning}</Card>}

      <Card>
        <button className="btn sm" onClick={() => setSchools(!schools)}>{t.schoolsHeat}</button>
        {schools && (
          <div className="tbl-wrap" style={{ maxHeight: 420, overflow: 'auto', marginTop: 12 }}><table className="heat">
            <thead><tr><th /> {hs.columns.map((c: string) => <th key={c} title={c} style={{ textAlign: 'center' }}>{c.slice(0, 7)}</th>)}</tr></thead>
            <tbody>{hs.rows.map((r: Any) => (
              <tr key={r.school}><td className="lbl">{r.school}</td>{r.values.map((v: number | null, i: number) => <td key={i} style={{ background: heatColor(v) }}>{v == null ? '' : pct(v)}</td>)}</tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      <Details title={t.howCalc}><p>{d.method}</p></Details>
    </div>
  )
}

/* ---------- Шаг 3. Учебники ---------- */
function Forest({ rows, lo, hi }: { rows: Any[]; lo: number; hi: number }) {
  const W = 620, rowH = 54
  const x = (v: number) => 130 + ((v - lo) / (hi - lo)) * (W - 160)
  return (
    <svg viewBox={`0 0 ${W} ${rows.length * rowH + 34}`} role="img" aria-label="forest" className="forest">
      <line x1={x(0)} x2={x(0)} y1={0} y2={rows.length * rowH + 8} stroke="currentColor" strokeOpacity=".4" strokeDasharray="4 4" />
      {rows.map((r, i) => (
        <g key={i} transform={`translate(0 ${i * rowH + 28})`}>
          <text x={0} y={4}>{r.label}</text>
          {r.naive != null && <circle cx={x(r.naive)} cy={-8} r={6} fill="#fb7185"><title>{r.naive.toFixed(1)}</title></circle>}
          {r.insufficient ? <text x={x(0) + 10} y={14} style={{ fill: 'var(--warn)' }}>—</text> : (
            <><line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={14} y2={14} stroke="#5eead4" strokeWidth={4} strokeLinecap="round" />
              <circle cx={x(r.est)} cy={14} r={6} fill="#5eead4"><title>{r.est.toFixed(1)}</title></circle></>
          )}
        </g>
      ))}
      {[lo, 0, hi].map((v) => <text key={v} x={x(v)} y={rows.length * rowH + 26} textAnchor="middle" style={{ fill: 'var(--faint)' }}>{v}</text>)}
    </svg>
  )
}

export function Why({ t, w, close }: { t: Tr; w: Any; close: () => void }) {
  return (
    <div className="modal" onClick={close} role="dialog" aria-modal="true">
      <Card glow className="" >
        <div onClick={(e) => e.stopPropagation()}>
          <h3 className="h2">{w.headline ?? w.error}</h3>
          {w.data && <p><b>{t.whatWeSee}:</b> {w.data}</p>}
          {w.evidence && <p>{w.evidence}</p>}
          {w.uncertainty && <p className="muted">{w.uncertainty}</p>}
          {w.method && <Details title={t.howCalc}>{w.method}</Details>}
          {w.limits && <><b>{t.assumptions}:</b><ul className="muted small">{w.limits.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></>}
          {w.scope && <p className="faint small">{w.scope}</p>}
          <button className="btn primary" onClick={close}>{t.close}</button>
        </div>
      </Card>
    </div>
  )
}

function TbOverview({ t, d, trust }: { t: Tr; d: Any; trust: (s: string) => React.ReactNode }) {
  const names: string[] = d.table.map((r: Any) => r.textbook)
  const [base, setBase] = useState<string>(d.reference)
  const pair = (a: string, b: string) => d.pairs.find((p: Any) => p.a === a && p.b === b)
  return (
    <Card>
      <h2 className="h2" style={{ margin: 0 }}>{t.listTitle}</h2>
      <p className="muted small">{t.listNote}</p>
      <div className="row" role="group" aria-label={t.baseLabel} style={{ margin: '10px 0' }}>
        <span className="muted small">{t.baseLabel}:</span>
        {names.map((n) => <button key={n} className={`btn sm ${n === base ? 'primary' : ''}`} aria-pressed={n === base} onClick={() => setBase(n)}>{n}</button>)}
      </div>
      <div className="tbl-wrap"><table>
        <thead><tr><th>{t.tbCol}</th><th>{t.schoolsCol}</th><th>{t.studentsCol}</th><th>{t.meanCol}</th><th>{t.vsCol} {base}</th><th>{t.statusCol}</th></tr></thead>
        <tbody>{d.table.map((r: Any) => {
          const p = r.textbook === base ? null : pair(r.textbook, base)
          return (
            <tr key={r.textbook} className={r.textbook === base ? 'hl' : ''}>
              <td><b>{r.textbook}</b></td><td>{r.schools}</td><td>{r.students}</td><td>{f1(r.naive_mean)}</td>
              <td>{p ? (p.status === 'insufficient' ? <span className="faint">—</span> : <><b>{sg(p.estimate)}</b> <span className="faint small">[{sg(p.ci[0])}; {sg(p.ci[1])}]</span></>) : <span className="faint">{t.baseSelf}</span>}</td>
              <td>{p ? trust(p.status) : null}</td>
            </tr>
          )
        })}</tbody>
      </table></div>

      <h3 className="h2" style={{ marginTop: 22 }}>{t.matrixTitle}</h3>
      <p className="muted small">{t.matrixNote}</p>
      <div className="tbl-wrap"><table>
        <thead><tr><th />{names.map((n) => <th key={n}>{n}</th>)}</tr></thead>
        <tbody>{names.map((a) => (
          <tr key={a}><td><b>{a}</b></td>{names.map((b) => {
            if (a === b) return <td key={b} className="faint">·</td>
            const p = pair(a, b)
            if (!p || p.status === 'insufficient') return <td key={b} className="faint" title={p?.status_text}>—</td>
            const color = !p.significant ? undefined : p.estimate > 0 ? 'var(--ok)' : '#fb7185'
            return (
              <td key={b} title={`[${sg(p.ci[0])}; ${sg(p.ci[1])}] ${t.pp}`}
                style={{ color, fontWeight: p.significant ? 700 : 400, outline: p.significant ? `1px solid ${color}` : undefined, outlineOffset: -3, borderRadius: 8 }}>
                {sg(p.estimate)}
              </td>
            )
          })}</tr>
        ))}</tbody>
      </table></div>
    </Card>
  )
}

export function StepTextbooks({ t, d, id }: { t: Tr; d: Any; id: string }) {
  const [why, setWhy] = useState<Any>(null)
  if (!d.available) return <Card className="err">{t.noTb}<br /><span className="muted small">{d.reason}</span></Card>
  const cmp: Any[] = d.comparisons
  const worst = cmp.some((c) => c.status === 'insufficient') ? 'insufficient' : cmp.some((c) => c.status === 'tentative') ? 'tentative' : 'ok'
  const rows = cmp.map((c) => ({ label: `${c.textbook} ${t.pp === 'п.п.' ? 'против' : 'қарсы'} ${c.vs}`, naive: c.naive_diff, est: c.estimate, ci: c.ci, insufficient: c.status === 'insufficient' }))
  const all = rows.flatMap((r) => [r.naive, r.ci[0], r.ci[1]])
  const lo = Math.floor(Math.min(-2, ...all) - 1), hi = Math.ceil(Math.max(2, ...all) + 1)
  const flipped = cmp.find((c) => c.status !== 'insufficient' && Math.sign(c.naive_diff) !== Math.sign(c.estimate))
  const trust = (s: string) => s === 'ok' ? <Badge tone="ok" icon="check">{t.trustOk}</Badge> : s === 'tentative' ? <Badge tone="warn" icon="warn">{t.trustTent}</Badge> : <Badge tone="bad" icon="warn">{t.trustNo}</Badge>
  return (
    <div className="stack">
      <Verdict title={t.whatWeSee} badge={trust(worst)}>
        {cmp.map((c) => (
          <p key={c.textbook}>
            {c.status === 'insufficient' ? t.v3Insuff(c.textbook, Math.min(c.schools, c.schools_ref))
              : c.significant ? t.v3Sig(c.textbook, c.vs, sg(c.estimate), sg(c.ci[0]), sg(c.ci[1]))
                : t.v3No(c.textbook)}
          </p>
        ))}
        {flipped && <p className="muted" style={{ fontSize: 16 }}>{t.v3Simpson(flipped.textbook, sg(flipped.naive_diff))}</p>}
      </Verdict>

      {cmp.map((c) => (
        <Card key={c.textbook}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 className="h2" style={{ margin: 0 }}>{c.textbook} <span className="muted" style={{ fontWeight: 400 }}>/ {t.reference} {c.vs}</span></h2>
            <div className="row">{trust(c.status)}<button className="btn sm" onClick={async () => setWhy(await j(`/why/textbook?id=${id}&textbook=${c.textbook}`))}>{t.why}</button></div>
          </div>
          <div className="compare" style={{ marginTop: 14 }}>
            <div className="card naive"><span className="muted small">{t.naiveLabel} <Hint text={t.hNaive} /></span>
              <div className="big">{sg(c.naive_diff)} <small className="muted" style={{ fontSize: 14, fontWeight: 400 }}>{t.pp}</small></div></div>
            <div className="card adj"><span className="muted small">{t.adjLabel} <Hint text={t.hAdj} /></span>
              {c.status === 'insufficient' ? <div style={{ paddingTop: 8 }}><Badge tone="bad">{t.trustNo}</Badge></div> : <>
                <div className="big">{sg(c.estimate)} <small className="muted" style={{ fontSize: 14, fontWeight: 400 }}>{t.pp}</small></div>
                <div className="muted small">[{sg(c.ci[0])}; {sg(c.ci[1])}] <Hint text={t.hCI} /></div></>}
            </div>
          </div>
          <div className="row small muted" style={{ marginTop: 10 }}>
            <span>{c.schools} / {c.schools_ref} {t.schoolsCol}</span>
            {c.status === 'tentative' && <span style={{ color: 'var(--warn)' }}>{t.trustTentWhy}</span>}
            {c.robust && c.status !== 'insufficient' && <span style={{ color: c.robust_agrees ? 'var(--ok)' : 'var(--warn)' }}>
              {t.robust}: {sg(c.robust.estimate)} [{sg(c.robust.ci[0])}; {sg(c.robust.ci[1])}] — {c.robust_agrees ? t.robustAgree : t.robustDisagree}</span>}
          </div>
        </Card>
      ))}

      <Card>
        <div className="forest-wrap"><Forest rows={rows} lo={lo} hi={hi} /></div>
        <div className="row small muted"><span style={{ color: '#fb7185' }}>● {t.naiveLabel}</span><span style={{ color: '#5eead4' }}>● {t.adjLabel}</span></div>
      </Card>

      {d.pairs && <TbOverview t={t} d={d} trust={trust} />}

      {d.simpson && (
        <Card>
          <div className="row"><h2 className="h2" style={{ margin: 0 }}>{t.simpsonTitle}</h2><Hint text={t.hSimpson} /></div>
          <p className="muted small">{t.whySimpsonText}</p>
          <div className="tbl-wrap"><table>
            <thead><tr><th>{t.schoolType}</th>{d.simpson.columns.map((c: string) => <th key={c}>{c}</th>)}<th>{t.schoolsCol}</th></tr></thead>
            <tbody>{d.simpson.rows.map((r: Any) => (
              <tr key={r.school_type}><td>{r.school_type}</td>{r.means.map((m: number | null, i: number) => <td key={i}>{m == null ? '' : f1(m)}</td>)}<td className="muted">{r.schools.join(' / ')}</td></tr>
            ))}</tbody>
          </table></div>
        </Card>
      )}

      <Card>
        <div className="row"><h2 className="h2" style={{ margin: 0 }}>{t.topicEff}</h2><Hint text={t.hFDR} /></div>
        <p className="muted small">{t.topicEffNote}</p>
        <div className="tbl-wrap"><table>
          <thead><tr><th /><th>{t.topicCol}</th><th>{t.devCol}</th><th>{t.diffCol}</th><th /></tr></thead>
          <tbody>{d.topic_effects.slice(0, 8).map((e: Any, i: number) => (
            <tr key={i} className={e.significant_dev ? 'hl' : ''}><td><b>{e.textbook}</b></td><td>{e.topic}</td>
              <td><b>{sg(e.deviation)}</b> <span className="faint small">[{sg(e.dev_ci[0])}; {sg(e.dev_ci[1])}]</span></td>
              <td className="muted">{sg(e.estimate)}</td>
              <td>{e.gated ? <Badge tone="bad">{t.trustNo}</Badge> : e.significant_dev ? <Badge tone="ok" icon="check">{t.trustOk}</Badge> : null}</td></tr>
          ))}</tbody>
        </table></div>
      </Card>
      <p className="faint small"><Icon name="info" size={14} /> {t.caveat}</p>
      <Details title={t.howCalc}><p>{d.method}</p></Details>
      {why && <Why t={t} w={why} close={() => setWhy(null)} />}
    </div>
  )
}

/* ---------- Шаг 4. Часы ---------- */
export function StepHours({ t, d, id }: { t: Tr; d: Any; id: string }) {
  const [plan, setPlan] = useState<Record<string, number>>({})
  const [fc, setFc] = useState<Any>(null)
  const [why, setWhy] = useState<Any>(null)
  const cur = useMemo(() => Object.fromEntries((d.rows ?? []).map((r: Any) => [r.topic, r.current])), [d])
  const rec = useMemo(() => Object.fromEntries((d.rows ?? []).map((r: Any) => [r.topic, r.recommended])), [d])
  useEffect(() => { setPlan(cur) }, [cur])
  const total = Object.values(plan).reduce((a, b) => a + b, 0)
  useEffect(() => {
    if (!d.available || !Object.keys(plan).length) return
    if (total !== d.total) { setFc({ error: `${t.sum}: ${total} / ${d.total}` }); return }
    const h = setTimeout(async () => { try { setFc(await post(`/optimize/scenario?id=${id}`, { plan })) } catch (e: Any) { setFc({ error: e.message }) } }, 250)
    return () => clearTimeout(h)
  }, [plan, total, d, id, t.sum])
  if (!d.available) return <Card className="err">{t.noHours}<br /><span className="muted small">{d.reason}</span></Card>
  const incl0 = d.gain_ci[0] <= 0 && d.gain_ci[1] >= 0
  return (
    <div className="stack">
      <Verdict title={t.whatWeSee} badge={<Badge tone={incl0 ? 'warn' : 'ok'} icon={incl0 ? 'warn' : 'check'}>{incl0 ? t.trustTent : t.trustOk}</Badge>}>
        <p>{incl0 ? t.v4None : t.v4Some(sg(d.gain_pp, 2))}</p>
        <p className="muted" style={{ fontSize: 15 }}>{t.v4Scope}</p>
      </Verdict>

      <Card>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="row">
            <button className="btn primary sm" onClick={() => setPlan(rec)}>{t.applyRec}</button>
            <button className="btn sm" onClick={() => setPlan(cur)}>{t.reset}</button>
          </div>
          <Badge tone={total === d.total ? 'ok' : 'bad'}>{t.sum}: {total} / {d.total}</Badge>
        </div>
        <div className="tbl-wrap" style={{ marginTop: 14 }}><table>
          <thead><tr><th>{t.topicCol}</th><th>{t.cur}</th><th style={{ minWidth: 190 }}>{t.plan}</th><th>{t.rec}</th><th>{t.range}</th><th /></tr></thead>
          <tbody>{d.rows.map((r: Any) => {
            const v = plan[r.topic] ?? r.current, oob = v < r.min || v > r.max, dlt = v - r.current
            return (
              <tr key={r.topic} className={oob ? 'hl' : ''}>
                <td>{r.topic}</td><td>{r.current}</td>
                <td><div className="row" style={{ flexWrap: 'nowrap', gap: 8 }}>
                  <input className="slider" type="range" min={1} max={r.max + 3} value={v} aria-label={r.topic} onChange={(e) => setPlan({ ...plan, [r.topic]: +e.target.value })} />
                  <b style={{ width: 22 }}>{v}</b><span className={dlt > 0 ? 'tag-up' : dlt < 0 ? 'tag-down' : 'faint'} style={{ width: 24 }}>{dlt ? sg(dlt, 0) : ''}</span></div>
                  {oob && <div className="small" style={{ color: 'var(--warn)' }}>{t.bounds} [{r.min}–{r.max}]</div>}</td>
                <td><b>{r.recommended}</b> <span className={r.delta > 0 ? 'tag-up' : r.delta < 0 ? 'tag-down' : 'faint'}>{r.delta ? sg(r.delta, 0) : ''}</span></td>
                <td className="muted">{r.range[0]}–{r.range[1]}</td>
                <td><button className="btn sm" onClick={async () => setWhy(await j(`/why/hours?id=${id}&topic=${encodeURIComponent(r.topic)}`))}>{t.why}</button></td>
              </tr>
            )
          })}</tbody>
        </table></div>
      </Card>

      <Card glow>
        <span className="eyebrow">{t.forecast}</span>
        {fc?.error ? <p style={{ color: 'var(--bad)' }}>{fc.error}</p> : fc && (
          <div className="row" style={{ alignItems: 'baseline' }}>
            <span className="stat-v">{sg(fc.gain_pp, 2)}</span><span className="muted">{t.forecastU}</span>
            <span className="muted small">[{sg(fc.gain_ci[0], 2)}; {sg(fc.gain_ci[1], 2)}] <Hint text={t.hCI} /></span>
          </div>
        )}
        <p className="muted small">{d.gain_note}</p>
      </Card>

      <Details title={t.assumptions}><ul>{d.assumptions.map((a: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{a}</li>)}</ul></Details>
      {why && <Why t={t} w={why} close={() => setWhy(null)} />}
    </div>
  )
}

/* ---------- Шаг 5. Записка ---------- */
export function StepReport({ t, id, lang, onCheck }: { t: Tr; id: string; lang: 'ru' | 'kz'; onCheck: () => void }) {
  const [rl, setRl] = useState<'ru' | 'kz'>(lang)
  const [llm, setLlm] = useState(false)
  const link = (fmt: string) => `${API}/report?id=${id}&lang=${rl}&fmt=${fmt}&llm=${llm}`
  return (
    <div className="stack">
      <Card glow>
        <div className="grid g2" style={{ alignItems: 'center' }}>
          <div>
            <h3 className="h3">{t.reportIncludes}</h3>
            <ul className="muted" style={{ paddingLeft: 18 }}>{t.reportItems.map((x) => <li key={x} style={{ marginBottom: 4 }}>{x}</li>)}</ul>
          </div>
          <div className="stack">
            <label className="field">{t.lang}
              <select value={rl} onChange={(e) => setRl(e.target.value as 'ru' | 'kz')}><option value="ru">Русский</option><option value="kz">Қазақша</option></select></label>
            <label className="row small"><input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} /> {t.llm} <Hint text={t.llmHint} /></label>
            <div className="row">
              <a className="btn primary" href={link('docx')}><Icon name="download" size={18} /> {t.download} DOCX</a>
              <a className="btn" href={link('pdf')}><Icon name="download" size={18} /> {t.download} PDF</a>
            </div>
            {rl === 'kz' && <p className="small" style={{ color: 'var(--warn)', margin: 0 }}><Icon name="warn" size={14} /> {t.kzNote}</p>}
          </div>
        </div>
      </Card>
      <button className="btn" onClick={onCheck}><Icon name="shield" size={18} /> {t.viewCheck}</button>
    </div>
  )
}

/* ---------- Проверка метода ---------- */
export function Validation({ t }: { t: Tr }) {
  const [v, setV] = useState<Any>(null)
  useEffect(() => { j('/validation').then(setV).catch(() => setV({})) }, [])
  if (!v) return <Card><p className="muted">…</p></Card>
  const tb = v.textbooks
  const hr: Any[] = v.hours ?? []
  const variants = Array.from(new Set(hr.map((r) => r.variant)))
  const mean = (a: number[]) => a.reduce((x, y) => x + y, 0) / (a.length || 1)
  return (
    <div className="stack">
      <Card glow><p className="lead" style={{ maxWidth: 'none' }}>{t.valIntro}</p></Card>
      {tb && (
        <div className="grid g4">
          <Card><Stat tone="ok" value={`${tb.ci_coverage}/${tb.n_seeds}`} label={t.valCover} hint={t.hCI} /></Card>
          <Card><Stat tone="ok" value={`${tb.robust_coverage}/${tb.n_seeds}`} label={t.valRobust} /></Card>
          <Card><Stat tone="warn" value={`${tb.naive_wrong}/${tb.n_seeds}`} label={t.valNaive} /></Card>
          <Card><Stat value={f1(tb.rho_irt_mean, 2)} label={`${t.valRho} (min ${f1(tb.rho_irt_min, 2)})`} hint={t.hIRT} /></Card>
        </div>
      )}
      <p className="small" style={{ color: 'var(--warn)' }}><Icon name="warn" size={14} /> {t.valNaiveNote}</p>
      {hr.length > 0 && (
        <Card>
          <h2 className="h2">{t.valHours}</h2>
          <div className="tbl-wrap"><table>
            <thead><tr><th /><th>0</th><th>0,5</th><th>1,0</th></tr></thead>
            <tbody>{variants.map((vn) => (
              <tr key={String(vn)}><td>{String(vn)}</td>{[0, 0.5, 1].map((tl) => {
                const rows = hr.filter((r) => r.variant === vn && r.tilt === tl)
                const g = mean(rows.map((r) => r.gain_true_pp))
                return <td key={tl} className={g < 0 ? 'tag-down' : 'tag-up'}>{sg(g, 3)} <span className="faint small">({t.valBest} {sg(mean(rows.map((r) => r.optimum_true_pp)), 3)})</span></td>
              })}</tr>
            ))}</tbody>
          </table></div>
          <p className="muted small">{t.valHoursNote}</p>
        </Card>
      )}
      {!tb && !hr.length && <Card>{t.valNone}</Card>}
    </div>
  )
}
