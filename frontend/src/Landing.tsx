import { useRef, useState } from 'react'
import { API } from './api'
import type { T as TT } from './i18n'
import { Card, Icon } from './ui'

type Tr = (typeof TT)['ru']

export function Landing({ t, onDemo, onUpload, busy, hasData, onContinue }: {
  t: Tr; onDemo: (n: string) => void; onUpload: (f: FileList | File[]) => void; busy: boolean; hasData: boolean; onContinue: () => void
}) {
  const [over, setOver] = useState(false)
  const [names, setNames] = useState<string[]>([])
  const input = useRef<HTMLInputElement>(null)
  const pick = (files: FileList | File[] | null) => {
    if (!files || !files.length) return
    setNames(Array.from(files).map((f) => f.name))
    onUpload(files)
  }
  const go = () => document.getElementById('start')?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  return (
    <div>
      <section className="hero" id="about">
        <div>
          <span className="eyebrow"><Icon name="spark" size={16} /> {t.heroEyebrow}</span>
          <h1>{t.heroA} <span className="accent">{t.heroAccent}</span>{t.heroB}</h1>
          <p className="lead">{t.heroLead}</p>
          <div className="cta">
            <button className="btn primary" disabled={busy} onClick={() => onDemo('main')}>{t.ctaDemo} <Icon name="arrow" size={18} /></button>
            <button className="btn" onClick={go}><Icon name="upload" size={18} /> {t.ctaUpload}</button>
            {hasData && <button className="btn" onClick={onContinue}>{t.next} <Icon name="arrow" size={18} /></button>}
          </div>
          <div className="trust-row">
            {t.trust.map((x, i) => <span key={i}><Icon name={i === 2 ? 'shield' : 'check'} size={16} /> {x}</span>)}
          </div>
        </div>
        <div className="stage" aria-hidden="true">
          <div className="orb" />
          <div className="float a"><span>{t.floatA}</span><b>{t.floatAv}</b><span>{t.floatAu}</span></div>
          <div className="float b"><span>{t.floatB}</span><b style={{ color: '#5eead4' }}>{t.floatBv}</b><span>{t.floatBu}</span></div>
          <div className="float c"><span>{t.floatC}</span><b>{t.floatCv}</b><span>{t.floatCu}</span></div>
        </div>
      </section>
      <p className="faint small" style={{ textAlign: 'center', marginTop: 0 }}>{t.floatNote}</p>

      <section className="section" id="features">
        <div className="section-head"><span className="eyebrow">{t.featTitle}</span><h2 className="h2">{t.featSub}</h2></div>
        <div className="grid g4">
          {t.feats.map(([ico, title, text]) => (
            <Card key={title} className="feature">
              <div className="ico-wrap"><Icon name={ico} size={24} /></div>
              <h3 className="h3">{title}</h3><p className="muted small" style={{ margin: 0 }}>{text}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><h2 className="h2">{t.howTitle}</h2></div>
        <div className="steps-line">
          {t.how.map(([title, text]) => (<Card key={title}><h3 className="h3">{title}</h3><p className="muted small" style={{ margin: 0 }}>{text}</p></Card>))}
        </div>
      </section>

      <section className="section" id="start">
        <div className="section-head"><span className="eyebrow">{t.navStart}</span><h2 className="h2">{t.startTitle}</h2><p className="lead">{t.startLead}</p></div>
        <div className="grid g2">
          <div className="grid">
            <button className="card feature btn-card" disabled={busy} onClick={() => onDemo('main')} style={{ textAlign: 'left', cursor: 'pointer', color: 'inherit' }}>
              <div className="ico-wrap"><Icon name="grid" size={24} /></div><h3 className="h3">{t.demoMain}</h3><span className="muted small">{t.demoMainD}</span>
            </button>
            <button className="card feature btn-card" disabled={busy} onClick={() => onDemo('small')} style={{ textAlign: 'left', cursor: 'pointer', color: 'inherit' }}>
              <div className="ico-wrap"><Icon name="flask" size={24} /></div><h3 className="h3">{t.demoSmall}</h3><span className="muted small">{t.demoSmallD}</span>
            </button>
          </div>
          <div>
            <div
              className={`dropzone ${over ? 'over' : ''}`} role="button" tabIndex={0}
              onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files) }}
            >
              <Icon name="upload" size={34} />
              <h3 className="h3" style={{ marginTop: 10 }}>{t.dropTitle}</h3>
              <p className="muted small" style={{ margin: 0 }}>{t.dropHint}</p>
              <p className="faint small" style={{ margin: '6px 0 0' }}>{t.dropFormats}</p>
              {names.length > 0 && <div className="chips" aria-label={t.filesSelected}>{names.map((n) => <span className="chip" key={n}>{n}</span>)}</div>}
              <input ref={input} type="file" multiple accept=".csv,.xlsx,.xls" hidden onChange={(e) => pick(e.target.files)} />
            </div>
            <div className="row" style={{ marginTop: 12, justifyContent: 'space-between' }}>
              <a href={`${API}/templates`} className="btn sm"><Icon name="download" size={16} /> {t.templates}</a>
              <span className="faint small"><Icon name="shield" size={14} /> {t.privacy}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <Card glow>
          <h2 className="h2">{t.honestTitle}</h2>
          <div className="grid g2" style={{ marginTop: 14 }}>
            {t.honest.map((h, i) => <div key={i} className="row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}><span style={{ color: 'var(--acc)', marginTop: 2 }}><Icon name="check" size={18} /></span><span className="muted">{h}</span></div>)}
          </div>
        </Card>
      </section>

      <footer className="foot"><span>{t.footA}</span><span>{t.footB}</span></footer>
    </div>
  )
}
