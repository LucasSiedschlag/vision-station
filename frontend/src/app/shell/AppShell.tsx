import { LogOut, Monitor, Moon, Search, Sun, User } from 'lucide-react'
import { Fragment, useEffect, useRef, useState } from 'react'
import { Outlet, useNavigate } from 'react-router'
import { logout } from '@/api/auth'
import { useLive } from '@/api/live'
import { useSession } from '@/api/session'
import { StatusStrip } from '@/components/domain/StatusStrip'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarGroup,
  SidebarHeader,
  SidebarLink,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { connectionOf } from '@/features/operator/view'
import { cn } from '@/lib/cn'
import { atLeast } from '@/lib/permissions'
import { useTheme } from '@/lib/theme'
import { text } from '@/texts'
import { screens, type Area } from '../routes'

const COLLAPSED_KEY = 'vision-station-nav-collapsed'

const areas: Area[] = ['operation', 'setup', 'analysis', 'system']

function NavRail() {
  const role = useSession((s) => s.role)
  const visible = screens.filter((screen) => atLeast(role, screen.min))
  const groups = areas
    .map((area) => visible.filter((screen) => screen.area === area))
    .filter((group) => group.length > 0)
  return (
    <Sidebar label={text.shell.menu}>
      <SidebarHeader>Vision Station</SidebarHeader>
      {groups.map((group, i) => (
        <Fragment key={group[0]!.area}>
          {i > 0 ? <SidebarSeparator /> : null}
          <SidebarGroup>
            {group.map(({ path, label, icon }) => (
              <SidebarLink key={path} to={path} label={label} icon={icon} end={path === '/'} />
            ))}
          </SidebarGroup>
        </Fragment>
      ))}
      <SidebarTrigger collapseLabel={text.shell.collapse} expandLabel={text.shell.expand} />
    </Sidebar>
  )
}

/** Ctrl+K (or the button in the top bar): go to any screen of the role by typing its name. */
function CommandPalette() {
  const role = useSession((s) => s.role)
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const search = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const visible = screens.filter((screen) => atLeast(role, screen.min))
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" aria-keyshortcuts="Control+K">
          <Search aria-hidden className="size-4" />
          {text.shell.palette}
          <kbd className="rounded-control border border-line px-1 font-mono text-xs text-fg-muted">
            Ctrl K
          </kbd>
        </Button>
      </DialogTrigger>
      <DialogContent
        title={text.shell.palette}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          search.current?.focus()
        }}
      >
        <Command label={text.shell.palette}>
          <CommandInput ref={search} placeholder={text.shell.palettePlaceholder} />
          <CommandList>
            <CommandEmpty>{text.shell.paletteEmpty}</CommandEmpty>
            <CommandGroup heading={text.shell.paletteScreens}>
              {visible.map(({ path, label, icon: Icon }) => (
                <CommandItem
                  key={path}
                  value={label}
                  onSelect={() => {
                    setOpen(false)
                    void navigate(path)
                  }}
                >
                  <Icon aria-hidden className="size-4 text-fg-muted" />
                  {label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
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
    <SidebarProvider storageKey={COLLAPSED_KEY}>
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
            <div className="flex items-center gap-2">
              <CommandPalette />
              <UserMenu />
            </div>
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
    </SidebarProvider>
  )
}
