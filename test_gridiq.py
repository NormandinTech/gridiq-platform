// GridIQ — AI Analytics Page (connected to forecast API)
import { Brain, TrendingUp, Zap, AlertTriangle } from 'lucide-react'
import { DemandForecastChart, RenewableForecastChart } from '../components/ForecastCharts'
import { useDemandForecast, useRenewableForecast, useAIRecommendations } from '../hooks/useGridData'
import { clsx } from 'clsx'
import type { RenewableStatus } from '../types'

const statusBadge: Record<RenewableStatus, { bg: string; text: string; label: string }> = {
  on_target:   { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', label: 'On target' },
  wind_drop:   { bg: 'bg-amber-100  dark:bg-amber-900/30',  text: 'text-amber-700  dark:text-amber-400',  label: 'Wind drop' },
  peak_risk:   { bg: 'bg-red-100    dark:bg-red-900/30',    text: 'text-red-700    dark:text-red-400',    label: 'Peak risk' },
  reserve_low: { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-400', label: 'Reserve low' },
  recovering:  { bg: 'bg-blue-100   dark:bg-blue-900/30',   text: 'text-blue-700   dark:text-blue-400',   label: 'Recovering' },
}

const recIcons: Record<string, string> = {
  bess_precharge:    '⚡',
  wind_ramp_warning: '🌬️',
  market_import:     '🔄',
}

export function AIAnalyticsPage() {
  const { data: demand,    isLoading: demandLoading }    = useDemandForecast(48)
  const { data: renewable, isLoading: renewLoading }     = useRenewableForecast(12)
  const { data: recsData,  isLoading: recsLoading }      = useAIRecommendations()

  const recs  = recsData?.recommendations ?? []
  const renPts = renewable?.points ?? []

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      {/* Model info banner */}
      <div className="flex items-center gap-3 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-xl px-4 py-3">
        <Brain size={18} className="text-violet-600 flex-shrink-0" />
        <div>
          <div className="text-xs font-semibold text-violet-800 dark:text-violet-300">
            GreenGrid Neural v3.2 — last inference {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
          <div className="text-[11px] text-violet-600 dark:text-violet-400 mt-0.5">
            Temporal Fusion Transformer · 8 years training data · RMSE 42 MW on 4-hour horizon
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Demand forecast */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-1">
            <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">48-hour demand forecast</div>
            {demand && (
              <div className="flex gap-3 text-[10px] font-mono text-slate-400">
                <span>Peak {demand.summary.peak_mw.toLocaleString()} MW</span>
                <span>Avg {demand.summary.avg_mw.toLocaleString()} MW</span>
              </div>
            )}
          </div>
          <div className="text-[10px] text-slate-400 mb-3">Confidence interval shown in band</div>
          {demandLoading
            ? <div className="h-44 flex items-center justify-center text-slate-400 text-sm">Loading forecast...</div>
            : <DemandForecastChart points={demand?.points ?? []} />
          }
        </div>

        {/* Renewable forecast table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1">Renewable output forecast</div>
          <div className="text-[10px] text-slate-400 mb-3">Next 12 hours · solar + wind combined</div>
          {renewLoading
            ? <div className="h-44 flex items-center justify-center text-slate-400 text-sm">Loading...</div>
            : (
              <>
                <RenewableForecastChart points={renPts} />
                <div className="mt-3 space-y-0">
                  {renPts.slice(0, 6).map((p) => {
                    const cfg = statusBadge[p.status]
                    return (
                      <div key={p.hour_offset} className="flex items-center gap-3 py-1.5 border-b border-slate-50 dark:border-slate-700/50 last:border-0">
                        <span className="text-[10px] text-slate-400 font-mono w-8">+{p.hour_offset}h</span>
                        <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all"
                               style={{ width: `${Math.min(100, (p.total_renewable_mw / 4000) * 100)}%` }} />
                        </div>
                        <span className="text-[10px] font-mono font-medium text-slate-700 dark:text-slate-300 w-20 text-right tabular-nums">
                          {p.total_renewable_mw.toLocaleString()} MW
                        </span>
                        <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-mono w-20 text-center', cfg.bg, cfg.text)}>
                          {cfg.label}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </>
            )
          }
        </div>
      </div>

      {/* AI Recommendations */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={15} className="text-blue-500" />
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">AI dispatch recommendations</span>
          {recsData && (
            <span className="text-[10px] font-mono text-slate-400 ml-auto">
              Generated {new Date(recsData.generated_at).toLocaleTimeString()}
            </span>
          )}
        </div>
        {recsLoading
          ? <div className="text-sm text-slate-400 py-4 text-center">Generating recommendations...</div>
          : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {recs.map((rec, i) => (
                <div key={i} className={clsx(
                  'rounded-lg p-3 border',
                  rec.priority === 'urgent'
                    ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
                    : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
                )}>
                  <div className="flex items-start gap-2">
                    <span className="text-lg">{rec.icon}</span>
                    <div>
                      <div className={clsx('text-xs font-semibold',
                        rec.priority === 'urgent' ? 'text-amber-800 dark:text-amber-300' : 'text-blue-800 dark:text-blue-300'
                      )}>
                        {rec.title}
                      </div>
                      <div className={clsx('text-[11px] mt-1 leading-snug',
                        rec.priority === 'urgent' ? 'text-amber-700 dark:text-amber-400' : 'text-blue-700 dark:text-blue-400'
                      )}>
                        {rec.description}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {recs.length === 0 && (
                <div className="col-span-3 text-center text-slate-400 text-sm py-6">
                  <Zap size={24} className="mx-auto mb-2 text-emerald-400" />
                  All systems optimally dispatched — no actions needed
                </div>
              )}
            </div>
          )
        }
      </div>
    </div>
  )
}
