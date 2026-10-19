import { ChevronDown, Layers } from 'lucide-react'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import { LAYERS, countOn, useLayers } from './layers'

const v = text.editor.view

/**
 * *Marcações* (docs/frontend.md §18): one split button above the image. The button turns every overlay on or off (key
 * `M`), the arrow opens the menu with a check per layer and what it shows.
 */
export function LayerMenu() {
  const { master, on, setMaster, toggle } = useLayers()
  useEffect(() => {
    const press = (e: KeyboardEvent) => {
      const t = e.target
      if (
        e.key.toLowerCase() !== 'm' ||
        e.ctrlKey ||
        e.metaKey ||
        e.altKey ||
        (t instanceof HTMLElement &&
          (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))
      )
        return
      useLayers.getState().setMaster(!useLayers.getState().master)
    }
    window.addEventListener('keydown', press)
    return () => window.removeEventListener('keydown', press)
  }, [])
  return (
    <div role="group" aria-label={text.editor.view.markingsMenu} className="inline-flex">
      <Button
        variant={master ? 'secondary' : 'ghost'}
        aria-pressed={master}
        className="rounded-r-none"
        onClick={() => setMaster(!master)}
      >
        <Layers aria-hidden className="size-4" />
        {v.markings(master ? countOn(on) : 0, LAYERS.length)}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant={master ? 'secondary' : 'ghost'}
            aria-label={v.markingsMenu}
            className="rounded-l-none border-l border-line"
          >
            <ChevronDown aria-hidden className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-64">
          <DropdownMenuCheckboxItem checked={master} onCheckedChange={setMaster}>
            {v.allMarkings}
          </DropdownMenuCheckboxItem>
          <DropdownMenuSeparator />
          {LAYERS.map((layer) => (
            <DropdownMenuCheckboxItem
              key={layer}
              checked={on[layer]}
              disabled={!master}
              onCheckedChange={(checked) => toggle(layer, checked === true)}
              className="items-start"
            >
              <span className="flex flex-col">
                <span>{v.layers[layer]}</span>
                <span className={cn('text-xs text-fg-muted')}>{v.layerHints[layer]}</span>
              </span>
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
