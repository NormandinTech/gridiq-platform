// GridIQ — Asset Health Table
import { clsx } from 'clsx'
import type { Asset } from '../types'
import { useGridStore } from '../stores/gridStore'

function HealthBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all duration-500', color)}
             style={{ width: `${score}%` }} />
      </div>
      <span className={clsx('text-xs font-mono font-medium tabular-nums',
        score >= 80 ? 'text-emerald-600 dark:text-emerald-400'
          : score >= 60 ? 'text-amber-600 dark:text-amber-400'
          : 'text-red-600 dark:text-red-400'
      )}>
        {score.toFixed(0)}%
      </span>
    </div>
  )
}

const statusDot: Record<string, string> = {
  online:      'bg-emerald-400',
  offline:     'bg-red-400 animate-pulse',
  degraded:    'bg-amber-400 animate-pulse',
  maintenance: 'bg-blue-400',
  unknown:     'bg-slate-400',
}

const typeLabel: Record<string, string> = {
  transformer:    'Transformer',
  circuit_breaker:'C. Breaker',
  capacitor_bank: 'Capacitor',
  rtu:            'RTU',
  solar_farm:     'Solar',
  wind_farm:      'Wind',
  bess:           'BESS',
  substation:     'Substation',
  gas_peaker:     'Peaker',
  smart_meter:    'Meter',
}

interface AssetTableProps {
  assets: Asset[]
  maxHeight?: string
}

export function AssetHealthTable({ assets, maxHeight = '400px' }: AssetTableProps) {
  const setSelected = useGridStore((s) => s.setSelectedAsset)
  const selectedId  = useGridStore((s) => s.selectedAssetId)

  const sorted = [...assets].sort((a, b) => a.health_score - b.health_score)

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-700">
        <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">Asset health</span>
        <span className="text-[10px] text-slate-400 font-mono">{assets.length} assets monitored</span>
      </div>
      <div style={{ maxHeight }} className="overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/80 backdrop-blur">
            <tr>
              <th className="text-left px-4 py-2 text-[10px] font-mono uppercase text-slate-400 tracking-wider">Asset</th>
              <th className="text-left px-4 py-2 text-[10px] font-mono uppercase text-slate-400 tracking-wider hidden md:table-cell">Type</th>
              <th className="text-left px-4 py-2 text-[10px] font-mono uppercase text-slate-400 tracking-wider">Health</th>
              <th className="text-left px-4 py-2 text-[10px] font-mono uppercase text-slate-400 tracking-wider hidden sm:table-cell">Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((asset) => (
              <tr
                key={asset.id}
                onClick={() => setSelected(asset.id === selectedId ? null : asset.id)}
                className={clsx(
                  'border-b border-slate-50 dark:border-slate-700/50 cursor-pointer transition-colors',
                  asset.id === selectedId
                    ? 'bg-blue-50 dark:bg-blue-900/20'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-700/30',
                )}
              >
                <td className="px-4 py-2.5">
                  <div className="font-medium text-slate-800 dark:text-slate-200 text-xs leading-tight">
                    {asset.name}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">{asset.asset_tag}</div>
                </td>
                <td className="px-4 py-2.5 hidden md:table-cell">
                  <span className="text-[10px] bg-slate-100 dark:bg-slate-700 text-slate-500 px-2 py-0.5 rounded font-mono">
                    {typeLabel[asset.asset_type] ?? asset.asset_type}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <HealthBar score={asset.health_score} />
                </td>
                <td className="px-4 py-2.5 hidden sm:table-cell">
                  <div className="flex items-center gap-1.5">
                    <div className={clsx('w-1.5 h-1.5 rounded-full', statusDot[asset.status] ?? 'bg-slate-400')} />
                    <span className="text-[10px] text-slate-500 capitalize">{asset.status}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
