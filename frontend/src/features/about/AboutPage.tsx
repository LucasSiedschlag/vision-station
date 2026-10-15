import { useAbout } from '@/api/queries/about'
import { describeError } from '@/api/mutations'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { text } from '@/texts'

export function AboutPage() {
  const about = useAbout()
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold">{text.about.title}</h1>
      {about.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : about.isError ? (
        <Card>
          <ErrorState
            message={text.about.loadError}
            detail={describeError(about.error)}
            onRetry={() => void about.refetch()}
          />
        </Card>
      ) : (
        <>
          <Card>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
                <dt className="text-fg-muted">{text.about.version}</dt>
                <dd className="font-mono tabular-nums">{about.data.version}</dd>
                <dt className="text-fg-muted">{text.about.jobFormat}</dt>
                <dd className="font-mono tabular-nums">{about.data.job_format}</dd>
              </dl>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{text.about.tools}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Ferramenta</TH>
                    <TH className="text-right">Versão</TH>
                  </TR>
                </THead>
                <TBody>
                  {about.data.tools.map((tool) => (
                    <TR key={`${tool.name}-${tool.version}`}>
                      <TD className="font-mono">{tool.name}</TD>
                      <TD numeric>{tool.version}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </main>
  )
}
