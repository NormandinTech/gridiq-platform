// GridIQ — Asset Intelligence Page
// Universal fault detection across all energy asset types.
// Covers: hydro/dams, solar, wind, gas, BESS, transmission, smart meters.

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import {
  Zap, AlertTriangle, TrendingDown, Wrench,
  Activity, DollarSign, BookOpen, ChevronRight,
} from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'
const get  = (p: string) => fetch(`${BASE}${p}`).then(r => r.json())
const post = (p: string) => fetch(`${BASE}${p}`, { method: 'POST' }).then(r => r.json())

// ── Config ────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'faults',    label: 'Active Faults',   icon: AlertTriangle },
  { id: 'outages',   label: 'Outages',          icon: Zap },
  { id: 'losses',    label: 'Energy Losses',    icon: TrendingDown },
  { id: 'workorders',label: 'Work Orders',      icon: Wrench },
  { id: 'bytype',    label: 'By Asset Type',    icon: Activity },
  { id: 'library',   label: 'Fault Library',    icon: BookOpen },
]

const SEV_CFG: Record<string, any> = {
  critical: { bg:'bg-red-50 dark:bg-red-900/20',    text:'text-red-700 dark:text-red-400',    dot:'bg-red-500 animate-pulse',   bar:'bg-red-500'    },
  high:     { bg:'bg-amber-50 dark:bg-amber-900/20', text:'text-amber-700 dark:text-amber-400', dot:'bg-amber-500 animate-pulse', bar:'bg-amber-500'  },
  medium:   { bg:'bg-blue-50 dark:bg-blue-900/20',   text:'text-blue-700 dark:text-blue-400',   dot:'bg-blue-400',               bar:'bg-blue-500'   },
  low:      { bg:'bg-slate-50 dark:bg-slate-800',    text:'text-slate-500 dark:text-slate-400', dot:'bg-slate-400',              bar:'bg-emerald-500'},
}

const CAT_ICON: Record<string, string> = {
  outage:          '🔴', partial_loss:'🟠', efficiency_loss:'📉',
  mechanical:      '⚙️',  electrical:  '⚡', thermal:        '🌡️',
  structural:      '🏗️',  hydraulic:   '💧', communication:  '📡',
  security:        '🔒', environmental:'🌿', compliance:     '📋',
}

const ASSET_EMOJI: Record<string, string> = {
  hydro_plant:'💧', dam:'🏞️', solar_farm:'☀️', wind_farm:'🌬️',
  gas_peaker:'🔥',  bess:'🔋', transmission_line:'⚡', substation:'🏭',
  smart_meter:'📊', transformer:'🔌', circuit_breaker:'⚡', thermal_plant:'🏭',
}

const PRIORITY_CFG: Record<string, any> = {
  immediate: { bg:'bg-red-100 dark:bg-red-900/30',    text:'text-red-700 dark:text-red-400',    label:'Immediate' },
  same_day:  { bg:'bg-amber-100 dark:bg-amber-900/30', text:'text-amber-700 dark:text-amber-400', label:'Same day'  },
  '7_days':  { bg:'bg-blue-100 dark:bg-blue-900/30',   text:'text-blue-700 dark:text-blue-400',   label:'7 days'   },
  scheduled: { bg:'bg-slate-100 dark:bg-slate-700',    text:'text-slate-500 dark:text-slate-400', label:'Scheduled'},
  monitor:   { bg:'bg-emerald-100 dark:bg-emerald-900/30', text:'text-emerald-700 dark:text-emerald-400', label:'Monitor'},
}

// ── Shared helpers ────────────────────────────────────────────────────────────

function KPI({ label, value, unit='', sub='', accent='', warn=false }: any) {
  return (
    <div className={clsx('bg-white dark:bg-slate-800 rounded-xl border px-4 py-3',
      accent ? `border-l-4 ${accent} border-slate-200 dark:border-slate-700`
              : 'border-slate-200 dark:border-slate-700',
    )}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-1">{label}</div>
      <div className={clsx('text-2xl font-bold tabular-nums', warn ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-slate-100')}>
        {value}<span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>
      </div>
      {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function FaultRow({ fault }: { fault: any }) {
  const [expanded, setExpanded] = useState(false)
  const sev = SEV_CFG[fault.severity] ?? SEV_CFG.low
  const qc = useQueryClient()
  const resolve = useMutation({
    mutationFn: () => post(`/asset-intelligence/faults/${fault.asset_id}/${fault.fault_code}/resolve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-faults'] })
      qc.invalidateQueries({ queryKey: ['ai-summary'] })
      qc.invalidateQueries({ queryKey: ['ai-outages'] })
      qc.invalidateQueries({ queryKey: ['ai-losses'] })
    },
  })

  return (
    <div className="border-b border-slate-50 dark:border-slate-700/50 last:border-0">
      <div className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/20 cursor-pointer transition-colors"
           onClick={() => setExpanded(!expanded)}>
        <div className={clsx('w-2 h-2 rounded-full flex-shrink-0 mt-1.5', sev.dot)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{fault.title}</span>
            <span className="text-[10px] font-mono text-slate-400">{fault.fault_code}</span>
            {fault.category && (
              <span className="text-[10px]">{CAT_ICON[fault.category] ?? '⚠️'}</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-[10px] text-slate-400 flex-wrap">
            <span>{ASSET_EMOJI[fault.asset_type] ?? '⚡'} {fault.asset_name}</span>
            <span>·</span>
            <span className={clsx('font-medium', sev.text)}>{fault.severity?.toUpperCase()}</span>
            {fault.estimated_loss_mw && (
              <span className="text-amber-500">{fault.estimated_loss_mw} MW loss</span>
            )}
            {fault.estimated_revenue_loss_hr && (
              <span className="text-red-500">${fault.estimated_revenue_loss_hr.toLocaleString()}/hr</span>
            )}
            <span>{formatDistanceToNow(new Date(fault.detected_at), { addSuffix: true })}</span>
          </div>
          {expanded && (
            <div className="mt-2 space-y-1.5 animate-fade-up">
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-snug">{fault.description}</p>
              {fault.trigger_param && (
                <div className="flex items-center gap-2 text-[10px] font-mono bg-slate-100 dark:bg-slate-700 rounded px-2 py-1 w-fit">
                  <span className="text-slate-500">{fault.trigger_param}:</span>
                  <span className="text-red-600 dark:text-red-400 font-bold">{fault.trigger_value}</span>
                  <span className="text-slate-400">/ threshold {fault.trigger_threshold}</span>
                </div>
              )}
              <p className="text-[11px] text-blue-600 dark:text-blue-400 font-medium">
                → {fault.recommended_action}
              </p>
              <div className="text-[10px] text-slate-400">
                Confidence: {Math.round((fault.confidence ?? 0) * 100)}% · Detection: {fault.maintenance_type}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {(() => {
            const p = PRIORITY_CFG[fault.work_order_priority]
            return p ? (
              <span className={clsx('text-[9px] px-1.5 py-0.5 rounded font-mono hidden sm:block', p.bg, p.text)}>
                {p.label}
              </span>
            ) : null
          })()}
          <ChevronRight size={12} className={clsx('text-slate-300 transition-transform', expanded && 'rotate-90')} />
        </div>
      </div>
      {expanded && (
        <div className="px-4 pb-3 flex gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); resolve.mutate() }}
            disabled={resolve.isPending}
            className="text-[10px] px-3 py-1.5 rounded border border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 transition-colors disabled:opacity-50"
          >
            {resolve.isPending ? 'Resolving...' : '✓ Mark resolved'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function AssetIntelligencePage() {
  const [tab, setTab] = useState('faults')
  const [sevFilter, setSevFilter] = useState('all')
  const [catFilter, setCatFilter] = useState('all')

  const { data: summary } = useQuery({ queryKey:['ai-summary'], queryFn:()=>get('/asset-intelligence/summary'), refetchInterval:30_000 })
  const { data: faultsData, isLoading: faultsLoading } = useQuery({
    queryKey: ['ai-faults', sevFilter, catFilter],
    queryFn: () => {
      const params = new URLSearchParams()
      if (sevFilter !== 'all') params.set('severity', sevFilter)
      if (catFilter !== 'all') params.set('category', catFilter)
      return get(`/asset-intelligence/faults?${params}&limit=100`)
    },
    refetchInterval: 20_000,
  })
  const { data: outagesData }  = useQuery({ queryKey:['ai-outages'],    queryFn:()=>get('/asset-intelligence/outages'),         refetchInterval:20_000 })
  const { data: lossesData }   = useQuery({ queryKey:['ai-losses'],     queryFn:()=>get('/asset-intelligence/energy-losses'),   refetchInterval:30_000 })
  const { data: woData }       = useQuery({ queryKey:['ai-workorders'], queryFn:()=>get('/asset-intelligence/work-orders'),     refetchInterval:30_000 })
  const { data: byTypeData }   = useQuery({ queryKey:['ai-bytype'],     queryFn:()=>get('/asset-intelligence/by-asset-type'),  refetchInterval:60_000 })
  const { data: libData }      = useQuery({ queryKey:['ai-library'],    queryFn:()=>get('/asset-intelligence/signatures'),      staleTime:Infinity })

  const faults = faultsData?.faults ?? []

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Sub-nav */}
      <div className="flex gap-0 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 overflow-x-auto flex-shrink-0">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={clsx('flex items-center gap-1.5 px-3 py-2.5 text-[11px] font-medium border-b-2 transition-colors whitespace-nowrap',
              tab === id
                ? 'border-blue-500 text-blue-700 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            )}>
            <Icon size={13} />{label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── Active Faults ────────────────────────────────────────────────── */}
        {tab === 'faults' && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <KPI label="Total active faults" value={summary?.total_active_faults ?? '—'} accent="border-l-blue-500" />
              <KPI label="Critical" value={summary?.critical ?? 0} warn={summary?.critical > 0} accent="border-l-red-500" />
              <KPI label="Outages" value={summary?.outages ?? 0} warn={summary?.outages > 0} accent="border-l-red-500" />
              <KPI label="MW lost" value={summary?.total_loss_mw ?? 0} unit="MW" accent="border-l-amber-500" sub={`$${(summary?.total_revenue_loss_hr ?? 0).toLocaleString()}/hr`} />
            </div>

            {/* Filters */}
            <div className="flex gap-2 flex-wrap">
              <div className="flex gap-1">
                {['all','critical','high','medium','low'].map(s => (
                  <button key={s} onClick={() => setSevFilter(s)}
                    className={clsx('text-[9px] font-mono uppercase px-2 py-1 rounded transition-colors',
                      sevFilter === s ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900'
                                      : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                    )}>{s}</button>
                ))}
              </div>
              <div className="flex gap-1 flex-wrap">
                {['all','outage','efficiency_loss','mechanical','electrical','thermal','structural','hydraulic'].map(c => (
                  <button key={c} onClick={() => setCatFilter(c)}
                    className={clsx('text-[9px] font-mono px-2 py-1 rounded transition-colors',
                      catFilter === c ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900'
                                      : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                    )}>
                    {CAT_ICON[c] ?? ''} {c.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">Detected faults — all asset types</span>
                <span className="text-[10px] text-slate-400 font-mono">click row to expand · resolve after maintenance</span>
              </div>
              <div style={{ maxHeight: '480px' }} className="overflow-y-auto">
                {faultsLoading
                  ? <div className="py-10 text-center text-slate-400 text-sm">Scanning fleet...</div>
                  : faults.length === 0
                    ? <div className="py-10 text-center text-slate-400 text-sm">No active faults matching filter</div>
                    : faults.map((f: any) => <FaultRow key={f.fault_id} fault={f} />)
                }
              </div>
            </div>
          </>
        )}

        {/* ── Outages ──────────────────────────────────────────────────────── */}
        {tab === 'outages' && outagesData && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <KPI label="Active outages" value={outagesData.count} warn={outagesData.count > 0} accent="border-l-red-500" />
              <KPI label="Total MW offline" value={outagesData.total_loss_mw} unit="MW" accent="border-l-red-500" />
              <KPI label="Revenue loss" value={`$${(outagesData.total_revenue_loss_per_hour ?? 0).toLocaleString()}`} sub="per hour" accent="border-l-amber-500" />
            </div>
            {outagesData.outages?.length === 0 ? (
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-emerald-200 p-10 text-center">
                <div className="text-3xl mb-2">✅</div>
                <div className="text-slate-600 dark:text-slate-400 font-medium">No active outages</div>
                <div className="text-slate-400 text-sm mt-1">All generation assets reporting output</div>
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-red-200 dark:border-red-800">
                <div className="px-4 py-3 border-b border-red-100 dark:border-red-800 flex items-center gap-2">
                  <Zap size={14} className="text-red-500" />
                  <span className="text-sm font-semibold text-red-700 dark:text-red-400">Generation outages</span>
                </div>
                {outagesData.outages.map((f: any) => <FaultRow key={f.fault_id} fault={f} />)}
              </div>
            )}
          </>
        )}

        {/* ── Energy Losses ────────────────────────────────────────────────── */}
        {tab === 'losses' && lossesData && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <KPI label="Assets below theoretical" value={lossesData.count} accent="border-l-amber-500" />
              <KPI label="Total MW lost" value={lossesData.total_loss_mw} unit="MW" accent="border-l-amber-500" />
              <KPI label="Revenue loss/hr" value={`$${(lossesData.total_revenue_loss_per_hour ?? 0).toLocaleString()}`} accent="border-l-red-500" />
              <KPI label="Annual impact" value={`$${((lossesData.annual_revenue_impact ?? 0) / 1_000_000).toFixed(1)}M`} accent="border-l-red-500" sub="projected" />
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 text-sm font-semibold text-slate-800 dark:text-slate-200">
                Assets operating below theoretical output
              </div>
              <div style={{ maxHeight: '440px' }} className="overflow-y-auto">
                {lossesData.losses?.map((f: any) => (
                  <div key={f.fault_id} className="flex items-start gap-3 px-4 py-3 border-b border-slate-50 dark:border-slate-700/50 last:border-0">
                    <span className="text-lg flex-shrink-0 mt-0.5">{ASSET_EMOJI[f.asset_type] ?? '⚡'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{f.asset_name}</span>
                        <span className="text-[10px] font-mono text-slate-400">{f.asset_type.replace(/_/g,' ')}</span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">{f.description}</p>
                      {f.trigger_value && (
                        <div className="mt-1 text-[10px] font-mono">
                          <span className="text-slate-400">Performance ratio: </span>
                          <span className="text-amber-600 font-bold">{(f.trigger_value * 100).toFixed(1)}%</span>
                          <span className="text-slate-400"> (target 95%)</span>
                        </div>
                      )}
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-sm font-bold text-amber-600">{f.estimated_loss_mw} MW</div>
                      <div className="text-[10px] text-red-500">${(f.estimated_revenue_loss_hr ?? 0).toLocaleString()}/hr</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── Work Orders ──────────────────────────────────────────────────── */}
        {tab === 'workorders' && woData && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <KPI label="Total work orders" value={woData.total} accent="border-l-blue-500" />
              <KPI label="Immediate dispatch" value={woData.immediate_count} warn={woData.immediate_count > 0} accent="border-l-red-500" />
              <KPI label="Total MW at risk" value={woData.total_loss_mw} unit="MW" accent="border-l-amber-500" />
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 text-sm font-semibold">
                AI-generated maintenance work orders — all asset types
              </div>
              <div style={{ maxHeight: '500px' }} className="overflow-y-auto divide-y divide-slate-50 dark:divide-slate-700/50">
                {woData.work_orders?.map((wo: any) => {
                  const p = PRIORITY_CFG[wo.priority]
                  return (
                    <div key={wo.work_order_id} className="flex items-start gap-3 px-4 py-3">
                      <span className={clsx('text-[9px] px-2 py-1 rounded-full font-mono font-bold flex-shrink-0 mt-0.5', p?.bg, p?.text)}>
                        {p?.label ?? wo.priority}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{wo.work_order_id}</span>
                          <span className="text-[10px] text-slate-400">{ASSET_EMOJI[wo.asset_type] ?? '⚡'} {wo.asset_name}</span>
                          <span className="text-[9px] font-mono text-slate-400">{wo.fault_code}</span>
                        </div>
                        <p className="text-[11px] text-slate-700 dark:text-slate-300 mt-0.5 font-medium">{wo.title}</p>
                        <p className="text-[11px] text-blue-600 dark:text-blue-400 mt-0.5">{wo.recommended_action}</p>
                        <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-400">
                          {wo.estimated_loss_mw && <span className="text-amber-500">{wo.estimated_loss_mw} MW loss</span>}
                          {wo.revenue_loss_hr && <span className="text-red-500">${wo.revenue_loss_hr.toLocaleString()}/hr</span>}
                          <span>Confidence {Math.round((wo.confidence ?? 0) * 100)}%</span>
                          <span className="capitalize">{wo.maintenance_type?.replace(/_/g,' ')}</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </>
        )}

        {/* ── By Asset Type ────────────────────────────────────────────────── */}
        {tab === 'bytype' && byTypeData && (
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 text-sm font-semibold">
              Fault distribution by energy asset type
            </div>
            {byTypeData.by_type?.map((t: any) => (
              <div key={t.asset_type} className="flex items-center gap-3 px-4 py-3 border-b border-slate-50 dark:border-slate-700/50 last:border-0">
                <span className="text-xl w-8 text-center">{ASSET_EMOJI[t.asset_type] ?? '⚡'}</span>
                <div className="flex-1">
                  <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 capitalize">
                    {t.asset_type.replace(/_/g, ' ')}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                    {t.critical > 0 && <span className="text-red-500">{t.critical} critical</span>}
                    {t.high > 0 && <span className="text-amber-500">{t.high} high</span>}
                    {t.outages > 0 && <span className="text-red-600 font-bold">{t.outages} outage</span>}
                    <span>{t.fault_count} total</span>
                  </div>
                </div>
                <div className="text-right">
                  {t.total_loss_mw > 0 && <div className="text-xs font-bold text-amber-600">{t.total_loss_mw} MW</div>}
                  {t.revenue_loss_hr > 0 && <div className="text-[10px] text-red-500">${t.revenue_loss_hr.toLocaleString()}/hr</div>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Fault Library ────────────────────────────────────────────────── */}
        {tab === 'library' && libData && (
          <>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-lg px-4 py-3 border border-slate-200 dark:border-slate-700">
              {libData.total} fault signatures monitoring {libData.asset_types_covered?.length} asset types across the generation and transmission fleet.
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
              <div style={{ maxHeight: '560px' }} className="overflow-y-auto divide-y divide-slate-50 dark:divide-slate-700/50">
                {libData.signatures?.map((s: any) => (
                  <div key={s.fault_code} className="flex items-start gap-3 px-4 py-3">
                    <span className="text-lg flex-shrink-0 mt-0.5">{CAT_ICON[s.category] ?? '⚠️'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-mono text-slate-400">{s.fault_code}</span>
                        <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{s.name}</span>
                        <span className={clsx('text-[9px] px-1.5 py-0.5 rounded font-mono',
                          SEV_CFG[s.severity]?.bg, SEV_CFG[s.severity]?.text
                        )}>{s.severity}</span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">{s.description}</p>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400 flex-wrap">
                        <span className="font-mono bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">{s.detection_method}</span>
                        {s.asset_types.map((at: string) => (
                          <span key={at}>{ASSET_EMOJI[at] ?? ''} {at.replace(/_/g,' ')}</span>
                        ))}
                        {s.nerc_standard && <span className="text-blue-500">{s.nerc_standard}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
