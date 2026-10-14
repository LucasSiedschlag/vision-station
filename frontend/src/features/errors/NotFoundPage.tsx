import { Link } from 'react-router'
import { texts } from '@/texts'

export function NotFoundPage() {
  return (
    <main className="p-8">
      <h1 className="text-2xl">{texts.errors.notFound}</h1>
      <Link to="/" className="underline">
        {texts.app.name}
      </Link>
    </main>
  )
}
