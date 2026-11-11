import { useCallback, useEffect, useState } from 'react'
import { j, post } from './api'
import { T, type Lang } from './i18n'
import { Landing } from './Landing'
import { StepData, StepHours, StepReport, StepTextbooks, StepTopics, Validation } from './Steps'
import { Card, Icon, Progress, StepHeader, type Any } from './ui'
import './index.css'

type View = 'landing' | 'app' | 'check'

function load<T>(key: string, fallback: T): T {
  try { return (localStorage.getItem(key) as unknown as T) ?? fallback } catch { return fallback }
}
function save(key: string, v: string) { try { localStorage.setItem(key, v) } catch { /* приватный режим */ } }

export default function App() {
  const [lang, setLang] = useState<Lang>(() => (load('ddc-lang', 'ru') as Lang))
  const [theme, setTheme] = useState<string>(() => load('ddc-theme', 'dark'))
  const t = T[lang]
  const [view, setView] = useState<View>('landing')
  const [step, setStep] = useState(0)
  const [id, setId] = useState<string | null>(null)
  const [quality, setQuality] = useState<Any>(null)
  const [synthetic, setSynthetic] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [diff, setDiff] = useState<Any>(null)
  const [tb, setTb] = useState<Any>(null)
  const [hours, setHours] = useState<Any>(null)
  const [dif, setDif] = useState<Any>(null)

  useEffect(() => { document.documentElement.dataset.theme = theme; save('ddc-theme', theme) }, [theme])
  useEffect(() => { document.documentElement.lang = lang === 'kz' ? 'kk' : 'ru'; save('ddc-lang', lang) }, [lang])

  const analyze = useCallback(async (rid: string) => {
    setBusy(true); setErr(''); setDiff(null); setTb(null); setHours(null); setDif(null)
    try {
      const [d, b, h, df] = await Promise.all([
        j(`/analyze/difficulty?id=${rid}`), j(`/analyze/textbooks?id=${rid}`), post(`/optimize/hours?id=${rid}`), j(`/analyze/dif?id=${rid}`),
      ])
      setDiff(d); setTb(b); setHours(h); setDif(df)
      return true
    } catch (e: Any) { setErr(String(e.message ?? e)); return false } finally { setBusy(false) }
  }, [])

  const start = useCallback(async (p: Promise<Any>) => {
    setBusy(true); setErr('')
    try {
      const r = await p
      setId(r.id); setQuality(r.quality); setSynthetic(r.synthetic)
      setView('app'); setStep(0); window.scrollTo({ top: 0 })
      await analyze(r.id)
    } catch (e: Any) { setErr(String(e.message ?? e)); setBusy(false) }
  }, [analyze])

  const demo = (n: string) => start(j(`/demo/${n}`, { method: 'POST' }))
  const upload = (files: FileList | File[]) => {
    const fd = new FormData()
    Array.from(files).forEach((f) => fd.append('files', f))
    start(j('/import', { method: 'POST', body: fd }))
  }
  const go = (n: number) => { setStep(n); setView('app'); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const ready = !!id && !busy && !!diff
  const total = t.steps.length
  const stepsDone = step

  const stepper = (
    <>
      {t.steps.map((name, i) => (
        <button key={name} className={`step-btn ${i < step ? 'done' : ''}`} aria-current={i === step ? 'step' : undefined}
          disabled={i > 0 && !ready} onClick={() => go(i)}>
          <span className="dot">{i < step ? <Icon name="check" size={15} /> : i + 1}</span><span>{name}</span>
        </button>
      ))}
    </>
  )

  return (
    <div className="shell">
      <a className="sr" href="#main">Skip to content</a>
      <header className="topbar">
        <button className="brand" onClick={() => setView('landing')} aria-label={t.navHome}>
          <span className="logo"><Icon name="layers" size={18} /></span><span className="name">{t.app}</span>
        </button>
        <nav className="topnav" aria-label="Main">
          <button onClick={() => { setView('landing'); setTimeout(() => document.getElementById('about')?.scrollIntoView({ behavior: 'smooth' }), 50) }}>{t.navAbout}</button>
          <button onClick={() => { setView('landing'); setTimeout(() => document.getElementById('start')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50) }}>{t.navStart}</button>
          <button onClick={() => setView('check')}>{t.navCheck}</button>
        </nav>
        <div className="top-actions">
          <div className="seg" role="group" aria-label={t.langLabel}>
            {(['ru', 'kz'] as Lang[]).map((l) => <button key={l} aria-pressed={l === lang} onClick={() => setLang(l)}>{l.toUpperCase()}</button>)}
          </div>
          <button className="icon-btn" aria-label={t.theme} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
          </button>
        </div>
      </header>
      {synthetic && view !== 'landing' && <div className="banner" role="note">{t.synth}</div>}

      <main id="main">
        {err && <Card className="err" ><b>{t.genericError}</b><br />{err}<div style={{ marginTop: 10 }}><button className="btn sm" onClick={() => { setErr(''); if (id) analyze(id) }}>{t.retry}</button></div></Card>}

        {view === 'landing' && (
          <Landing t={t} onDemo={demo} onUpload={upload} busy={busy} hasData={!!id} onContinue={() => go(step)} />
        )}

        {view === 'check' && (
          <div style={{ marginTop: 12 }}>
            <StepHeader n={0} total={0} eyebrow={t.navCheck} title={<>{t.valTitle[0]} <span className="accent">{t.valTitle[1]}</span></>} lead="" />
            <Validation t={t} />
          </div>
        )}

        {view === 'app' && (
          <>
            <div className="mobile-steps" role="tablist" aria-label={t.sidebarTitle}>
              {t.steps.map((name, i) => <button key={name} aria-current={i === step ? 'step' : undefined} disabled={i > 0 && !ready} onClick={() => go(i)}>{i + 1}. {name}</button>)}
            </div>
            <div className="workspace">
              <aside className="card stepper" aria-label={t.sidebarTitle}>
                <h2>{t.sidebarTitle}</h2>
                {stepper}
                <div className="progress-track" aria-hidden="true"><i style={{ width: `${(stepsDone / (total - 1)) * 100}%` }} /></div>
                <span className="faint small" style={{ marginLeft: 8 }}>{stepsDone}/{total - 1} {t.sidebarDone}</span>
              </aside>

              <section aria-live="polite">
                <StepHeader n={step + 1} total={total} eyebrow={t.stepWord}
                  title={step === 0 ? <>{t.s1Title[0]} <span className="accent">{t.s1Title[1]}</span></>
                    : step === 1 ? <>{t.s2Title[0]} <span className="accent">{t.s2Title[1]}</span></>
                      : step === 2 ? <>{t.s3Title[0]} <span className="accent">{t.s3Title[1]}</span></>
                        : step === 3 ? <>{t.s4Title[0]} <span className="accent">{t.s4Title[1]}</span></>
                          : <>{t.s5Title[0]} <span className="accent">{t.s5Title[1]}</span></>}
                  lead={step === 4 ? t.reportLead : t.stepsLead[step]} />

                {busy && <Progress messages={t.progress} />}
                {!busy && id && quality && step === 0 && <StepData t={t} quality={quality} id={id} reanalyze={analyze} busy={busy} />}
                {!busy && ready && step === 1 && <StepTopics t={t} d={diff} dif={dif} />}
                {!busy && ready && step === 2 && tb && <StepTextbooks t={t} d={tb} id={id!} />}
                {!busy && ready && step === 3 && hours && <StepHours t={t} d={hours} id={id!} />}
                {!busy && ready && step === 4 && <StepReport t={t} id={id!} lang={lang} onCheck={() => setView('check')} />}

                <div className="stepnav">
                  <button className="btn" disabled={step === 0} onClick={() => go(step - 1)}><Icon name="back" size={18} /> {t.back}</button>
                  {step < total - 1 && <button className="btn primary" disabled={!ready} onClick={() => go(step + 1)}>{step === 3 ? t.toReport : t.next} <Icon name="arrow" size={18} /></button>}
                </div>
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
