// GridIQ SaaS — Root App
// Handles auth routing, session restore, and route guards.

import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Suspense, lazy } from 'react'

import { useAuthStore } from './stores/authStore'
import { useGridStore } from './stores/gridStore'
import { authApi } from './services/authApi'

import { LoginPage }           from './pages/auth/LoginPage'
import { SignupPage }          from './pages/auth/SignupPage'
import { OnboardingWizard }    from './pages/auth/OnboardingWizard'
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from './pages/auth/AuthPages'
import { TopBar }              from './components/TopBar'
import { Sidebar }             from './components/Sidebar'
import { GridOverviewPage }    from './pages/GridOverview'
import { AIAnalyticsPage }     from './pages/AIAnalytics'
import { CybersecurityPage }   from './pages/Cybersecurity'
import { VegetationPage }      from './pages/Vegetation'
import { AssetIntelligencePage } from './pages/AssetIntelligence'
import { SettingsPage }        from './pages/SettingsPage'

const DigitalTwinPage      = lazy(() => import('./pages/stubs').then(m => ({ default: m.DigitalTwinPage })))
const RenewablesPage       = lazy(() => import('./pages/stubs').then(m => ({ default: m.RenewablesPage })))
const AlertsPage           = lazy(() => import('./pages/stubs').then(m => ({ default: m.AlertsPage })))
const MaintenancePage      = lazy(() => import('./pages/stubs').then(m => ({ default: m.MaintenancePage })))
const CompliancePage       = lazy(() => import('./pages/stubs').then(m => ({ default: m.CompliancePage })))
const SensorManagementPage = lazy(() => import('./pages/SensorManagement').then(m => ({ default: m.SensorManagementPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 30_000 } },
})

type AuthScreen = 'login' | 'signup' | 'forgot'

function getUrlInfo() {
  if (typeof window === 'undefined') return { page: null, token: null }
  const params = new URLSearchParams(window.location.search)
  const path   = window.location.pathname
  if (path.includes('verify-email'))   return { page: 'verify',  token: params.get('token') }
  if (path.includes('reset-password')) return { page: 'reset',   token: params.get('token') }
  return { page: null, token: null }
}

function DashboardLayout() {
  const activeTab    = useGridStore(s => s.activeTab)
  const setActiveTab = useGridStore(s => s.setActiveTab)

  const pages: Record<string, JSX.Element> = {
    overview:    <GridOverviewPage />,
    analytics:   <AIAnalyticsPage />,
    twin:        <DigitalTwinPage />,
    renewables:  <RenewablesPage />,
    vegetation:  <VegetationPage />,
    alerts:      <AlertsPage />,
    maintenance: <MaintenancePage />,
    security:    <CybersecurityPage />,
    compliance:  <CompliancePage />,
    assets:      <AssetIntelligencePage />,
    sensors:     <SensorManagementPage />,
    settings:    <SettingsPage />,
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-900 overflow-hidden">
      <TopBar onSettings={() => setActiveTab('settings')} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Suspense fallback={<div className="flex items-center justify-center h-full"><div className="text-slate-400 text-sm animate-pulse">Loading...</div></div>}>
            {pages[activeTab] ?? <GridOverviewPage />}
          </Suspense>
        </main>
      </div>
    </div>
  )
}

function AppContent() {
  const { isLoggedIn, isLoading, setAuth, setLoading, clearAuth } = useAuthStore()
  const tenant = useAuthStore(s => s.tenant)
  const [authScreen, setAuthScreen] = useState<AuthScreen>('login')
  const { page: urlPage, token: urlToken } = getUrlInfo()

  useEffect(() => {
    const restore = async () => {
      setLoading(true)
      try {
        const r = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
        if (r.ok) {
          const { access_token } = await r.json()
          const me = await authApi.me(access_token) as any
          setAuth(me.user, me.tenant, access_token)
        } else {
          clearAuth()
        }
      } catch {
        clearAuth()
      }
    }
    restore()
  }, [])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-slate-700 rounded-full animate-spin" />
      </div>
    )
  }

  if (urlPage === 'verify' && urlToken) {
    return <VerifyEmailPage token={urlToken} onVerified={(token, user, tenant) => {
      setAuth(user, tenant, token)
      window.history.replaceState({}, '', '/')
    }} />
  }

  if (urlPage === 'reset' && urlToken) {
    return <ResetPasswordPage token={urlToken} onSuccess={() => {
      window.history.replaceState({}, '', '/')
      setAuthScreen('login')
    }} />
  }

  if (!isLoggedIn) {
    if (authScreen === 'signup') return <SignupPage onSuccess={() => setAuthScreen('login')} onLogin={() => setAuthScreen('login')} />
    if (authScreen === 'forgot') return <ForgotPasswordPage onBack={() => setAuthScreen('login')} />
    return <LoginPage onLogin={() => {}} onSignup={() => setAuthScreen('signup')} onForgot={() => setAuthScreen('forgot')} />
  }

  if (tenant && !tenant.onboarding_complete) {
    return <OnboardingWizard onComplete={() => useAuthStore.getState().updateTenant({ onboarding_complete: true })} />
  }

  return <DashboardLayout />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}
