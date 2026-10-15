import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/feedback'
import { text } from '@/texts'

export function ForbiddenPage() {
  return (
    <main>
      <EmptyState
        heading="h1"
        icon={<ShieldAlert aria-hidden className="size-8" />}
        title={text.errors.forbiddenTitle}
        description={text.errors.forbiddenBody}
        action={
          <Link to="/" className={buttonVariants({ variant: 'primary' })}>
            {text.errors.backToStation}
          </Link>
        }
      />
    </main>
  )
}
