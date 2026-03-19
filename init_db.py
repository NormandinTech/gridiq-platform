// GridIQ — Custom React Hooks
// All data fetching with TanStack Query + auto-refresh intervals.
// These hooks are the single source of truth for backend-connected data.

import { useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  gridApi, assetApi, forecastApi, alertApi,
  maintenanceApi, securityApi, complianceApi,
  GridIQWebSocket,
} from '../services/api'
import { useGridStore } from '../stores/gridStore'

// ── Grid KPIs (refresh every 10s) ────────────────────────────────────────────

export function useGridKPIs() {
  const setKPIs = useGridStore((s) => s.setKPIs)
  const query = useQuery({
    queryKey: ['grid', 'kpis'],
    queryFn: gridApi.getKPIs,
    refetchInterval: 10_000,
    staleTime: 8_000,
  })
  useEffect(() => {
    if (query.data) setKPIs(query.data)
  }, [query.data, setKPIs])
  return query
}

export function useGridTopology() {
  return useQuery({
    queryKey: ['grid', 'topology'],
    queryFn: gridApi.getTopology,
    refetchInterval: 30_000,
    staleTime: 25_000,
  })
}

export function useEnergyMix() {
  return useQuery({
    queryKey: ['grid', 'energy-mix'],
    queryFn: gridApi.getEnergyMix,
    refetchInterval: 15_000,
  })
}

// ── Assets (refresh every 30s) ────────────────────────────────────────────────

export function useAssets(params?: { asset_type?: string; status?: string }) {
  return useQuery({
    queryKey: ['assets', params],
    queryFn: () => assetApi.list(params),
    refetchInterval: 30_000,
    staleTime: 20_000,
  })
}

export function useAsset(id: string | null) {
  return useQuery({
    queryKey: ['asset', id],
    queryFn: () => assetApi.get(id!),
    enabled: !!id,
    refetchInterval: 30_000,
  })
}

export function useAssetHealth(id: string | null) {
  return useQuery({
    queryKey: ['asset-health', id],
    queryFn: () => assetApi.getHealth(id!),
    enabled: !!id,
    refetchInterval: 20_000,
  })
}

export function useAssetTelemetry(id: string | null, hours = 24) {
  return useQuery({
    queryKey: ['asset-telemetry', id, hours],
    queryFn: () => assetApi.getTelemetry(id!, hours),
    enabled: !!id,
    refetchInterval: 30_000,
  })
}

// ── Forecasts (refresh every 5 minutes) ──────────────────────────────────────

export function useDemandForecast(horizonHours = 48) {
  return useQuery({
    queryKey: ['forecast', 'demand', horizonHours],
    queryFn: () => forecastApi.getDemand(horizonHours),
    refetchInterval: 5 * 60_000,
    staleTime: 4 * 60_000,
  })
}

export function useRenewableForecast(horizonHours = 12) {
  return useQuery({
    queryKey: ['forecast', 'renewable', horizonHours],
    queryFn: () => forecastApi.getRenewable(horizonHours),
    refetchInterval: 5 * 60_000,
  })
}

export function useAIRecommendations() {
  return useQuery({
    queryKey: ['forecast', 'recommendations'],
    queryFn: forecastApi.getRecommendations,
    refetchInterval: 2 * 60_000,
  })
}

// ── Alerts ────────────────────────────────────────────────────────────────────

export function useAlerts(params?: { status?: string; limit?: number }) {
  const setAlerts = useGridStore((s) => s.setAlerts)
  const query = useQuery({
    queryKey: ['alerts', params],
    queryFn: () => alertApi.list(params),
    refetchInterval: 15_000,
  })
  useEffect(() => {
    if (query.data) setAlerts(query.data.alerts)
  }, [query.data, setAlerts])
  return query
}

export function useAcknowledgeAlert() {
  const qc = useQueryClient()
  const ack = useGridStore((s) => s.acknowledgeAlert)
  return useMutation({
    mutationFn: ({ id, by }: { id: string; by: string }) =>
      alertApi.acknowledge(id, by),
    onSuccess: (_, { id, by }) => {
      ack(id, by)
      qc.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}

export function useResolveAlert() {
  const qc = useQueryClient()
  const resolve = useGridStore((s) => s.resolveAlert)
  return useMutation({
    mutationFn: (id: string) => alertApi.resolve(id),
    onSuccess: (_, id) => {
      resolve(id)
      qc.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}

// ── Maintenance ───────────────────────────────────────────────────────────────

export function useMaintenance(params?: { status?: string; priority?: string }) {
  return useQuery({
    queryKey: ['maintenance', params],
    queryFn: () => maintenanceApi.list(params),
    refetchInterval: 60_000,
  })
}

// ── Security ──────────────────────────────────────────────────────────────────

export function useSecurityPosture() {
  return useQuery({
    queryKey: ['security', 'posture'],
    queryFn: securityApi.getPosture,
    refetchInterval: 30_000,
  })
}

export function useThreats() {
  const setThreats = useGridStore((s) => s.setThreats)
  const query = useQuery({
    queryKey: ['security', 'threats'],
    queryFn: () => securityApi.getThreats(),
    refetchInterval: 15_000,
  })
  useEffect(() => {
    if (query.data) setThreats(query.data.threats)
  }, [query.data, setThreats])
  return query
}

export function useZoneStatuses() {
  return useQuery({
    queryKey: ['security', 'zones'],
    queryFn: securityApi.getZones,
    refetchInterval: 30_000,
  })
}

// ── Compliance ────────────────────────────────────────────────────────────────

export function useNERCCIP() {
  return useQuery({
    queryKey: ['compliance', 'nerc-cip'],
    queryFn: complianceApi.getNERCCIP,
    refetchInterval: 5 * 60_000,
    staleTime: 4 * 60_000,
  })
}

// ── WebSocket Hooks ───────────────────────────────────────────────────────────

export function useLiveTelemetry() {
  const pushReading = useGridStore((s) => s.pushReading)
  const setConnected = useGridStore((s) => s.setWsConnected)
  const wsRef = useRef<GridIQWebSocket | null>(null)

  useEffect(() => {
    const ws = new GridIQWebSocket(
      'telemetry',
      (data: any) => {
        if (data?.type === 'telemetry') {
          pushReading({
            asset_id: data.asset_id,
            asset_name: data.asset_name,
            asset_type: data.asset_type,
            timestamp: data.timestamp,
            readings: data.readings,
          })
        }
      },
      setConnected
    )
    ws.connect()
    wsRef.current = ws
    return () => ws.disconnect()
  }, [pushReading, setConnected])

  return wsRef.current
}

export function useLiveAlerts() {
  const addAlert = useGridStore((s) => s.addAlert)
  const setAlerts = useGridStore((s) => s.setAlerts)
  const wsRef = useRef<GridIQWebSocket | null>(null)

  useEffect(() => {
    const ws = new GridIQWebSocket('alerts', (data: any) => {
      if (data?.type === 'alert.snapshot') setAlerts(data.data)
      else if (data?.type === 'alert.created') addAlert(data.data)
    })
    ws.connect()
    wsRef.current = ws
    return () => ws.disconnect()
  }, [addAlert, setAlerts])
}

// ── System health ─────────────────────────────────────────────────────────────

export function useSystemHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/v1/health`)
        return res.ok ? await res.json() : null
      } catch {
        return null
      }
    },
    refetchInterval: 30_000,
    retry: false,
  })
}
