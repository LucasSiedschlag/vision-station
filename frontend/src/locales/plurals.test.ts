import { describe, expect, it } from 'vitest'
import { text } from '@/texts'

describe('plurals', () => {
  it('zero is not singular in Portuguese (CLDR puts 0 in "one" for pt)', () => {
    expect(text.dataset.total(0)).toBe('Nenhuma imagem no dataset')
    expect(text.dataset.total(1)).toBe('1 imagem no dataset')
    expect(text.dataset.total(3)).toBe('3 imagens no dataset')
    expect(text.access.revoked(0)).toBe('Nenhuma sessão encerrada.')
  })
})
