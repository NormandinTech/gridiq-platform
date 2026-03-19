@tailwind base;
@tailwind components;
@tailwind utilities;

/* ── Custom base styles ─────────────────────────────────────────────────────── */

@layer base {
  *, *::before, *::after {
    box-sizing: border-box;
  }

  html {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  body {
    @apply bg-slate-50 text-slate-900;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
  }

  :root {
    --sidebar-width: 208px;
    --sidebar-collapsed: 56px;
    --topbar-height: 48px;
  }

  /* Dark mode */
  .dark body {
    @apply bg-slate-900 text-slate-100;
  }
}

/* ── Scrollbar ───────────────────────────────────────────────────────────────── */

::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  @apply bg-slate-200 dark:bg-slate-700 rounded-full;
}
::-webkit-scrollbar-thumb:hover {
  @apply bg-slate-300 dark:bg-slate-600;
}

/* ── Animations ─────────────────────────────────────────────────────────────── */

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(12px); }
  to   { opacity: 1; transform: translateX(0); }
}

@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}

.animate-fade-up {
  animation: fadeUp 0.2s ease both;
}

.animate-slide-right {
  animation: slideInRight 0.2s ease both;
}

/* ── Skeleton loading ───────────────────────────────────────────────────────── */

.skeleton {
  background: linear-gradient(
    90deg,
    #f1f5f9 25%,
    #e2e8f0 50%,
    #f1f5f9 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}

.dark .skeleton {
  background: linear-gradient(
    90deg,
    #1e293b 25%,
    #334155 50%,
    #1e293b 75%
  );
  background-size: 200% 100%;
}

/* ── Recharts overrides ─────────────────────────────────────────────────────── */

.recharts-cartesian-grid-horizontal line,
.recharts-cartesian-grid-vertical line {
  stroke: #f1f5f9;
}

.dark .recharts-cartesian-grid-horizontal line,
.dark .recharts-cartesian-grid-vertical line {
  stroke: #1e293b;
}

.recharts-tooltip-wrapper {
  outline: none !important;
}

/* ── Tabular numbers for metrics ────────────────────────────────────────────── */

.tabular-nums {
  font-variant-numeric: tabular-nums;
}

/* ── Health bar transition ───────────────────────────────────────────────────── */

.health-bar {
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Stagger animation for list items ───────────────────────────────────────── */

.stagger > * {
  animation: fadeUp 0.2s ease both;
}
.stagger > *:nth-child(1)  { animation-delay: 0ms; }
.stagger > *:nth-child(2)  { animation-delay: 40ms; }
.stagger > *:nth-child(3)  { animation-delay: 80ms; }
.stagger > *:nth-child(4)  { animation-delay: 120ms; }
.stagger > *:nth-child(5)  { animation-delay: 160ms; }
.stagger > *:nth-child(6)  { animation-delay: 200ms; }
.stagger > *:nth-child(7)  { animation-delay: 240ms; }
.stagger > *:nth-child(8)  { animation-delay: 280ms; }
