// GridIQ — Alert Feed Component
// Live alert feed with severity badges, actions, and WebSocket updates.

import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'
import { AlertTriangle, CheckCircle, Info, XCircle, ChevronRight } from 'lucide-react'
import type { Alert, AlertSeverity } from '../types'
import { useAcknowledgeAlert, useResolveAlert } from '../hooks/useGridData'

// ── Severity config ───────────────────────────────────────────────────────────

const severityConfig: Record<AlertSeverity, {
  bg: string; text: string; border: string; icon: typeof AlertTriangle; label: string
}> = {
  critical: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    text: 'text-red-700 dark:text-red-400',
    border: 'border-red-200 dark:border-red-800',
    icon: XCircle,
    label: 'Critical',
  },
  high: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    text: 'text-amber-700 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
    icon: AlertTriangle,
    label: 'High',
  },
  medium: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-700 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800',
    icon: Info,
    label: 'Medium',
  },
  low: {
    bg: 'bg-slate-50 dark:bg-slate-800',
    text: 'text-slate-600 dark:text-slate-400',
    border: 'border-slate-200 dark:border-slate-700',
    icon: Info,
    label: 'Low',
  },
  info: {
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    text: 'text-emerald-700 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800',
    icon: CheckCircle,
    label: 'Info',
  },
}

// ── Single alert row ──────────────────────────────────────────────────────────

function AlertRow({ alert, onExpand }: { alert: Alert; onExpand: (id: string) => void }) {
  const cfg = severityConfig[alert.severity]
  const Icon = cfg.icon
  const ack = useAcknowledgeAlert()
  const resolve = useResolveAlert()
  const isResolved = alert.status === 'resolved'
  const isAcked = alert.status === 'acknowledged'

  return (
    <div
      className={clsx(
        'flex gap-3 px-4 py-3 border-b last:border-b-0 transition-all',
        'border-slate-100 dark:border-slate-800',
        isResolved && 'opacity-50',
      )}
    >
      {/* Icon */}
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5', cfg.bg)}>
        <Icon size={15} className={cfg.text} />
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2">
          <span className="text-[11px] font-medium flex-1 text-slate-800 dark:text-slate-200 leading-tight">
            {alert.title}
          </span>
          <span className={clsx(
            'text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full flex-shrink-0',
            cfg.bg, cfg.text,
          )}>
            {cfg.label}
          </span>
        </div>

        {alert.description && (
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-snug line-clamp-2">
            {alert.description}
          </p>
        )}

        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          <span className="text-[10px] text-slate-400 font-mono">
            {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
          </span>
          {alert.confidence && (
            <span className="text-[10px] text-slate-400">
              {Math.round(alert.confidence * 100)}% confidence
            </span>
          )}
          {alert.source === 'ai' && (
            <span className="text-[9px] bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-400 px-1.5 py-0.5 rounded font-mono">
              AI
            </span>
          )}
          {isAcked && (
            <span className="text-[9px] text-slate-400">
              ✓ acked by {alert.acknowledged_by}
            </span>
          )}
        </div>

        {/* Actions */}
        {!isResolved && (
          <div className="flex gap-2 mt-2">
            {!isAcked && (
              <button
                onClick={() => ack.mutate({ id: alert.id, by: 'operator' })}
                disabled={ack.isPending}
                className="text-[10px] px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
              >
                Acknowledge
              </button>
            )}
            {alert.recommended_action && (
              <button
                onClick={() => resolve.mutate(alert.id)}
                disabled={resolve.isPending}
                className="text-[10px] px-2 py-1 rounded border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 transition-colors disabled:opacity-50"
              >
                {alert.recommended_action.split(' ').slice(0, 3).join(' ')} ↗
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Alert Feed ────────────────────────────────────────────────────────────────

interface AlertFeedProps {
  alerts: Alert[]
  maxHeight?: string
  showFilters?: boolean
}

export function AlertFeed({ alerts, maxHeight = '420px', showFilters = true }: AlertFeedProps) {
  const [filter, setFilter] = useState<string>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const filtered = filter === 'all'
    ? alerts
    : alerts.filter((a) => a.severity === filter || a.status === filter)

  const counts = {
    critical: alerts.filter((a) => a.severity === 'critical' && a.status === 'open').length,
    high:     alerts.filter((a) => a.severity === 'high'     && a.status === 'open').length,
    open:     alerts.filter((a) => a.status === 'open').length,
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-700">
        <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
          Live alert feed
        </span>
        <div className="flex items-center gap-2">
          {counts.critical > 0 && (
            <span className="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-mono">
              {counts.critical} critical
            </span>
          )}
          <span className="text-[10px] bg-slate-100 dark:bg-slate-700 text-slate-500 px-2 py-0.5 rounded-full font-mono">
            {counts.open} open
          </span>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex gap-1 px-4 py-2 border-b border-slate-100 dark:border-slate-700 overflow-x-auto">
          {['all', 'critical', 'high', 'medium', 'open', 'acknowledged'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'text-[10px] font-mono uppercase px-2 py-1 rounded-md transition-colors whitespace-nowrap',
                filter === f
                  ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700',
              )}
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {/* List */}
      <div style={{ maxHeight }} className="overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <CheckCircle size={32} className="mb-2 text-emerald-400" />
            <p className="text-sm">No alerts matching this filter</p>
          </div>
        ) : (
          filtered.map((a) => (
            <AlertRow key={a.id} alert={a} onExpand={setExpanded} />
          ))
        )}
      </div>
    </div>
  )
}
