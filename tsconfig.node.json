// GridIQ — KPI Card Component
import { type ReactNode } from 'react'
import { clsx } from 'clsx'

interface KPICardProps {
  label: string
  value: string | number
  unit?: string
  delta?: string
  deltaType?: 'up' | 'down' | 'neutral' | 'warn'
  icon?: ReactNode
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'purple'
  pulse?: boolean
  onClick?: () => void
}

const accentBorder: Record<string, string> = {
  blue:   'border-l-blue-500',
  green:  'border-l-emerald-500',
  amber:  'border-l-amber-500',
  red:    'border-l-red-500',
  purple: 'border-l-violet-500',
}

const deltaColors: Record<string, string> = {
  up:      'text-emerald-500',
  down:    'text-red-500',
  warn:    'text-amber-500',
  neutral: 'text-slate-400',
}

export function KPICard({
  label, value, unit, delta, deltaType = 'neutral',
  icon, accent, pulse, onClick,
}: KPICardProps) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700',
        'px-4 py-3 flex flex-col gap-1 transition-shadow',
        accent && `border-l-4 ${accentBorder[accent]}`,
        onClick && 'cursor-pointer hover:shadow-md',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400 dark:text-slate-500">
          {label}
        </span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
          {value}
        </span>
        {unit && (
          <span className="text-xs text-slate-400 font-medium">{unit}</span>
        )}
        {pulse && (
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-1" />
        )}
      </div>
      {delta && (
        <span className={clsx('text-[11px] font-medium', deltaColors[deltaType])}>
          {delta}
        </span>
      )}
    </div>
  )
}
