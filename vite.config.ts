// GridIQ — Sidebar Navigation
import { clsx } from 'clsx'
import {
  LayoutDashboard, Cpu, TrendingUp, Leaf, Shield,
  Wrench, FileCheck, Radio, ChevronLeft, TreePine, Activity, Settings,
} from 'lucide-react'
import { useGridStore } from '../stores/gridStore'

const NAV_ITEMS = [
  { id: 'overview',    label: 'Grid Overview',    icon: LayoutDashboard },
  { id: 'analytics',  label: 'AI Analytics',      icon: TrendingUp },
  { id: 'twin',       label: 'Digital Twin',      icon: Cpu },
  { id: 'renewables', label: 'Renewables',        icon: Leaf },
  { id: 'vegetation', label: 'Vegetation Risk',   icon: TreePine },
  { id: 'assets',     label: 'Asset Intelligence', icon: Activity },
  { id: 'sensors',    label: 'Sensor Fleet',       icon: Radio },
  { id: 'settings',   label: 'Settings',           icon: Settings },
  { id: 'alerts',     label: 'Alerts',            icon: Radio },
  { id: 'maintenance',label: 'Maintenance',       icon: Wrench },
  { id: 'security',   label: 'Cybersecurity',     icon: Shield },
  { id: 'compliance', label: 'NERC CIP',          icon: FileCheck },
]

export function Sidebar() {
  const activeTab   = useGridStore((s) => s.activeTab)
  const setActiveTab = useGridStore((s) => s.setActiveTab)
  const sidebarOpen = useGridStore((s) => s.sidebarOpen)
  const toggle      = useGridStore((s) => s.toggleSidebar)
  const openAlerts  = useGridStore((s) => s.openAlerts)
  const activeThreats = useGridStore((s) => s.activeThreats)

  const alertBadge = openAlerts.filter((a) => a.status === 'open').length
  const threatBadge = activeThreats.filter((t) => t.is_active).length

  return (
    <aside
      className={clsx(
        'flex flex-col bg-slate-900 text-white transition-all duration-200 flex-shrink-0',
        sidebarOpen ? 'w-52' : 'w-14',
      )}
    >
      {/* Collapse toggle */}
      <div className="flex justify-end px-3 py-3 border-b border-slate-700/50">
        <button
          onClick={toggle}
          className="text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ChevronLeft
            size={16}
            className={clsx('transition-transform duration-200', !sidebarOpen && 'rotate-180')}
          />
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const badge = id === 'alerts' ? alertBadge : id === 'security' ? threatBadge : 0
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={clsx(
                'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors relative',
                activeTab === id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
              )}
            >
              <Icon size={16} className="flex-shrink-0" />
              {sidebarOpen && (
                <span className="text-xs font-medium truncate">{label}</span>
              )}
              {badge > 0 && (
                <span className={clsx(
                  'absolute text-[9px] font-bold bg-red-500 text-white rounded-full flex items-center justify-center',
                  sidebarOpen ? 'right-3 top-2.5 px-1.5 py-0.5' : 'right-1.5 top-1.5 w-4 h-4',
                )}>
                  {badge > 9 ? '9+' : badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      {sidebarOpen && (
        <div className="px-3 py-3 border-t border-slate-700/50">
          <div className="text-[9px] font-mono text-slate-600 leading-relaxed">
            <div>GridIQ Platform v1.0</div>
            <div>IEC 62443 · NERC CIP</div>
          </div>
        </div>
      )}
    </aside>
  )
}
