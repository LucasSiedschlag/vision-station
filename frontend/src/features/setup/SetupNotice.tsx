import { Link } from 'react-router'
import { useSetupOpen } from '@/api/queries/setup'
import { buttonVariants } from '@/components/ui/button'
import { text } from '@/texts'

/** On the operator screen of an installation nobody has set up: the way into the wizard, which needs no login yet. */
export function SetupNotice() {
  const open = useSetupOpen()
  if (!open.data?.open) return null
  return (
    <div
      role="region"
      aria-label={text.setup.title}
      className="mx-6 mb-2 flex flex-wrap items-center justify-between gap-3 rounded-card border border-warn bg-warn-surface px-4 py-2"
    >
      <span className="font-medium">{text.setup.notice}</span>
      <Link to="/setup" className={buttonVariants({ variant: 'primary' })}>
        {text.setup.noticeAction}
      </Link>
    </div>
  )
}
