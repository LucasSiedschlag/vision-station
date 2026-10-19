import '@testing-library/jest-dom/vitest'
import { i18n } from '@lingui/core'
import { configure } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { vi } from 'vitest'
import { messages } from '@/locales/pt-BR/messages.po'

// every test starts in Portuguese, the source language, with its catalog (TD-30)
i18n.loadAndActivate({ locale: 'pt-BR', messages })

// the whole-app tests are slow on a busy machine: wait longer before saying an element is not there
configure({ asyncUtilTimeout: 5000 })

// jsdom lacks a few browser APIs that Radix UI and the layout code use (skipped in the node-only tests).
if (typeof window !== 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    onchange: null,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.setPointerCapture ??= () => {}
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
}

// jsdom measures nothing, so every pixel is at (0, 0) and react-resizable-panels takes each click for a grab of a
// separator and swallows it. The panels are plain boxes here; the real thing is checked in the browser (e2e).
vi.mock('react-resizable-panels', () => {
  const box = ({ children, className }: { children?: ReactNode; className?: string }) =>
    createElement('div', { className }, children)
  return {
    Group: box,
    Panel: box,
    Separator: ({ 'aria-label': label }: { 'aria-label'?: string }) =>
      createElement('div', { role: 'separator', 'aria-label': label }),
    useDefaultLayout: () => ({ defaultLayout: undefined, onLayoutChanged: () => {} }),
  }
})
