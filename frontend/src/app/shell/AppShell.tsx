import { ChevronsLeft, ChevronsRight, LogOut, Monitor, Moon, Sun, User } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { logout } from '@/api/auth'
import { useLive } from '@/api/live'
import { useSession } from '@/api/session'
import { StatusStrip } from '@/components/domain/StatusStrip'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { connectionOf } from '@/features/operator/view'
import { cn } from '@/lib/cn'
import { atLeast } from '@/lib/permissions'
import { useTheme } from '@/lib/theme'
import { text } from '@/texts'
import { screens } from '../routes'

const COLLAPSED_KEY = 'vision-station-nav-collapsed'

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === '1'
    } catch {
      return false
    }
  })
  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1')
      } catch {
        /* ignore */
      }
      return !c
    })
  return [collapsed, toggle] as const
}

function NavRail() {
  const role = useSession((s) => s.role)
  const [collapsed, toggle] = useCollapsed()
  const visible = screens.filter((screen) => atLeast(role, screen.min))
  return (
    <nav
      aria-label={text.shell.menu}
      className={cn(
        'flex shrink-0 flex-col gap-1 border-r border-line bg-surface-1 p-2',
        collapsed ? 'w-16' : 'w-56',
      )}
    >
      <p className={cn('px-3 py-2 text-sm font-semibold', collapsed && 'sr-only')}>
        Vision Station
      </p>
      {visible.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          end={path === '/'}
          aria-label={collapsed ? label : undefined}
          className={({ isActive }) =>
            cn(
              'flex min-h-control items-center gap-3 rounded-control px-3 text-control hover:bg-surface-3',
              isActive && 'bg-surface-3 font-medium',
            )
          }
        >
          <Icon aria-hidden className="size-5 shrink-0" />
          <span className={cn(collapsed && 'sr-only')}>{label}</span>
        </NavLink>
      ))}
      <Button
        variant="ghost"
        className="mt-auto justify-start"
        onClick={toggle}
        aria-label={collapsed ? text.shell.expand : text.shell.collapse}
        aria-expanded={!collapsed}
      >
        {collapsed ? (
          <ChevronsRight aria-hidden className="size-5" />
        ) : (
          <ChevronsLeft aria-hidden className="size-5" />
        )}
        <span className={cn(collapsed && 'sr-only')}>{text.shell.collapse}</span>
      </Button>
    </nav>
  )
}

function UserMenu() {
  const role = useSession((s) => s.role)
  const { preference, setPreference } = useTheme()
  const themes = [
    { value: 'system', label: text.shell.themeSystem, icon: Monitor },
    { value: 'dark', label: text.shell.themeDark, icon: Moon },
    { value: 'light', label: text.shell.themeLight, icon: Sun },
  ] as const
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button aria-label={`${text.shell.user}: ${text.roles[role]}`}>
          <User aria-hidden className="size-4" />
          {text.roles[role]}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <p className="px-3 py-1 text-xs text-fg-muted">{text.shell.theme}</p>
        {themes.map(({ value, label, icon: Icon }) => (
          <DropdownMenuItem
            key={value}
            onSelect={() => setPreference(value)}
            aria-current={preference === value ? 'true' : undefined}
            className={cn(preference === value && 'font-medium')}
          >
            <Icon aria-hidden className="size-4" />
            {label}
            {preference === value ? <span className="sr-only"> (atual)</span> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut aria-hidden className="size-4" />
          {text.login.logout}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** The shell for a person with a login: menu by role, the job in use, the user menu, and the status strip at the bottom. */
export function AppShell() {
  const status = useLive((s) => s.status)
  const connected = useLive((s) => s.connected)
  const connecting = useLive((s) => s.connecting)
  const connection = connectionOf(connected, connecting)
  return (
    <div className="flex h-full bg-surface-0">
      <NavRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-line bg-surface-1 px-4 py-2">
          <p className="min-w-0 truncate text-base">
            {status?.job.name ? (
              <>
                <strong className="font-semibold">{status.job.name}</strong>{' '}
                <span className="text-fg-muted">v{status.job.version}</span>
              </>
            ) : (
              <span className="text-fg-muted">{text.shell.noJob}</span>
            )}
          </p>
          <UserMenu />
        </header>
        {connection === 'offline' ? (
          <p
            role="alert"
            className="border-b border-fail-text/40 bg-fail-surface px-4 py-2 text-sm text-fail-text"
          >
            Sem conexão com o programa da estação. O que aparece nesta tela pode estar
            desatualizado.
          </p>
        ) : null}
        <div id="content" tabIndex={-1} className="min-h-0 flex-1 overflow-auto outline-none">
          <Outlet />
        </div>
        <footer className="border-t border-line bg-surface-1 px-4 py-1">
          <StatusStrip status={status} connection={connection} />
        </footer>
      </div>
    </div>
  )
}
