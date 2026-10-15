import { SearchX } from 'lucide-react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/feedback'
import { text } from '@/texts'

export function NotFoundPage() {
  return (
    <main>
      <EmptyState
        heading="h1"
        icon={<SearchX aria-hidden className="size-8" />}
        title="Página não encontrada"
        description={text.errors.notFoundBody}
        action={
          <Link to="/" className={buttonVariants({ variant: 'primary' })}>
            {text.errors.backToStation}
          </Link>
        }
      />
    </main>
  )
}
