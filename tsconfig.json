// GridIQ — Forecast Charts (Recharts)
import { format } from 'date-fns'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend,
} from 'recharts'
import type { ForecastPoint, RenewableForecastPoint } from '../types'

// ── Demand Forecast Chart ─────────────────────────────────────────────────────

interface DemandChartProps {
  points: ForecastPoint[]
  historicalPoints?: ForecastPoint[]
}

export function DemandForecastChart({ points, historicalPoints = [] }: DemandChartProps) {
  const allPoints = [...historicalPoints, ...points]

  const data = allPoints.map((p, i) => ({
    time: format(new Date(p.timestamp), 'HH:mm'),
    value: Math.round(p.value_mw),
    lower: p.lower_ci_mw ? Math.round(p.lower_ci_mw) : undefined,
    upper: p.upper_ci_mw ? Math.round(p.upper_ci_mw) : undefined,
    isForecast: i >= historicalPoints.length,
  }))

  const nowIndex = historicalPoints.length

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.12} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="histGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1d4ed8" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 9, fill: '#94a3b8', fontFamily: 'monospace' }}
          interval={7}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fill: '#94a3b8' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${(v / 1000).toFixed(1)}GW`}
        />
        <Tooltip
          contentStyle={{
            fontSize: 11, border: '0.5px solid #e2e8f0',
            borderRadius: 8, background: 'white',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          }}
          formatter={(v: number) => [`${v.toLocaleString()} MW`]}
          labelStyle={{ color: '#64748b', fontSize: 10 }}
        />
        {/* CI band */}
        <Area dataKey="upper" fill="url(#ciGrad)" stroke="none" />
        <Area dataKey="lower" fill="white" stroke="none" />
        {/* Historical */}
        <Area
          dataKey="value"
          fill="url(#histGrad)"
          stroke="#1d4ed8"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3 }}
        />
        {/* Forecast starts */}
        {nowIndex > 0 && (
          <ReferenceLine
            x={data[nowIndex]?.time}
            stroke="#f59e0b"
            strokeDasharray="4 3"
            label={{ value: 'NOW', position: 'top', fontSize: 9, fill: '#f59e0b' }}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── Renewable Forecast Bar Chart ──────────────────────────────────────────────

const statusColor: Record<string, string> = {
  on_target:    '#22c55e',
  wind_drop:    '#f59e0b',
  peak_risk:    '#ef4444',
  reserve_low:  '#f97316',
  recovering:   '#3b82f6',
}

interface RenewableChartProps {
  points: RenewableForecastPoint[]
}

export function RenewableForecastChart({ points }: RenewableChartProps) {
  const data = points.map((p) => ({
    time: `+${p.hour_offset}h`,
    solar: Math.round(p.solar_mw),
    wind:  Math.round(p.wind_mw),
    total: Math.round(p.total_renewable_mw),
    status: p.status,
    note: p.note,
  }))

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} barGap={2} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 9, fill: '#94a3b8', fontFamily: 'monospace' }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fill: '#94a3b8' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${Math.round(v / 100) * 100}`}
        />
        <Tooltip
          contentStyle={{
            fontSize: 11, border: '0.5px solid #e2e8f0',
            borderRadius: 8, background: 'white',
          }}
          formatter={(v: number, name: string) => [`${v.toLocaleString()} MW`, name]}
          labelStyle={{ color: '#64748b', fontSize: 10, marginBottom: 4 }}
        />
        <Legend
          iconType="square"
          iconSize={8}
          wrapperStyle={{ fontSize: 10, fontFamily: 'monospace', paddingTop: 4 }}
        />
        <Bar dataKey="solar" fill="#f59e0b" radius={[2, 2, 0, 0]} name="Solar" />
        <Bar dataKey="wind"  fill="#3b82f6" radius={[2, 2, 0, 0]} name="Wind" />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── 24h Load vs Generation Sparkline ─────────────────────────────────────────

interface LoadGenChartProps {
  data: Array<{ time: string; load: number; gen: number }>
}

export function LoadVsGenerationChart({ data }: LoadGenChartProps) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 9, fill: '#94a3b8', fontFamily: 'monospace' }}
          interval={3}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fill: '#94a3b8' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${(v / 1000).toFixed(1)}G`}
        />
        <Tooltip
          contentStyle={{ fontSize: 11, borderRadius: 8, border: '0.5px solid #e2e8f0' }}
          formatter={(v: number) => [`${v.toLocaleString()} MW`]}
        />
        <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
        <Line
          type="monotone"
          dataKey="gen"
          stroke="#3b82f6"
          strokeWidth={1.5}
          dot={false}
          name="Generation"
        />
        <Line
          type="monotone"
          dataKey="load"
          stroke="#ef4444"
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 2"
          name="Demand"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
