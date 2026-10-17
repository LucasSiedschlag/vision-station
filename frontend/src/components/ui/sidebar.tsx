import { ChevronsLeft, ChevronsRight, type LucideIcon } from 'lucide-react'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router'
import { cn } from '@/lib/cn'
import { Button } from './button'
import { Tooltip } from './tooltip'

// The navigation rail of the shell (shadcn Sidebar pattern, TD-29, document 05 §4.2): groups of
// links separated by space and a divider, collapsible to icons. The state is remembered in this
// browser (not in a cookie); there is no Ctrl+B, so no key is taken from the pages.

interface SidebarState {
  collapsed: boolean
  toggle: () => void
}

const SidebarContext = createContext<SidebarState>({ collapsed: false, toggle: () => {} })

export const useSidebar = () => useContext(SidebarContext)

function read(key: string): boolean {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function write(key: string, collapsed: boolean) {
  try {
    localStorage.setItem(key, collapsed ? '1' : '0')
  } catch {
    /* a private window: the rail just opens expanded next time */
  }
}

export function SidebarProvider({
  storageKey,
  children,
}: {
  /** Where the collapsed state is remembered in this browser. */
  storageKey: string
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(() => read(storageKey))
  const toggle = () =>
    setCollapsed((c) => {
      write(storageKey, !c)
      return !c
    })
  return <SidebarContext.Provider value={{ collapsed, toggle }}>{children}</SidebarContext.Provider>
}

/** The rail: a navigation landmark with a name. */
export function Sidebar({ label, children }: { label: string; children: ReactNode }) {
  const { collapsed } = useSidebar()
  return (
    <nav
      aria-label={label}
      data-collapsed={collapsed || undefined}
      className={cn(
        'flex shrink-0 flex-col gap-1 overflow-y-auto border-r border-line bg-surface-1 p-2',
        collapsed ? 'w-16' : 'w-56',
      )}
    >
      {children}
    </nav>
  )
}

export function SidebarHeader({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebar()
  return <p className={cn('px-3 py-2 text-sm font-semibold', collapsed && 'sr-only')}>{children}</p>
}

/** One group of links. Groups are told apart by space and a divider, not by a heading. */
export function SidebarGroup({ children }: { children: ReactNode }) {
  return <ul className="flex flex-col gap-1">{children}</ul>
}

export function SidebarSeparator() {
  return <div role="none" className="mx-3 my-2 h-px bg-line" />
}

/**
 * A link of the rail. Collapsed, the label stays for screen readers (sr-only, never removed) and
 * shows as a tooltip on hover and focus.
 */
export function SidebarLink({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}) {
  const { collapsed } = useSidebar()
  const link = (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex min-h-control items-center gap-3 rounded-control text-control hover:bg-surface-3',
          collapsed ? 'justify-center' : 'px-3',
          isActive && 'bg-surface-3 font-medium',
        )
      }
    >
      <Icon aria-hidden className="size-5 shrink-0" />
      <span className={cn(collapsed && 'sr-only')}>{label}</span>
    </NavLink>
  )
  return (
    <li>
      {collapsed ? (
        <Tooltip content={label} side="right">
          {link}
        </Tooltip>
      ) : (
        link
      )}
    </li>
  )
}

/** The collapse button at the foot of the rail. */
export function SidebarTrigger({
  collapseLabel,
  expandLabel,
}: {
  collapseLabel: string
  expandLabel: string
}) {
  const { collapsed, toggle } = useSidebar()
  return (
    <Button
      variant="ghost"
      className="mt-auto justify-start"
      onClick={toggle}
      aria-label={collapsed ? expandLabel : collapseLabel}
      aria-expanded={!collapsed}
    >
      {collapsed ? (
        <ChevronsRight aria-hidden className="size-5" />
      ) : (
        <ChevronsLeft aria-hidden className="size-5" />
      )}
      <span className={cn(collapsed && 'sr-only')}>{collapseLabel}</span>
    </Button>
  )
}
