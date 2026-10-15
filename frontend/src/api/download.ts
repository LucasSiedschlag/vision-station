import { ApiError, type Problem } from './client'
import { useSession } from './session'

/** A file from the API that needs the login (an export, a backup), saved by the browser under `filename`. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const { token } = useSession.getState()
  const response = await fetch(`${location.origin}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    if (response.status === 401 && token) useSession.getState().expire()
    const problem = (await response.json().catch(() => undefined)) as Partial<Problem> | undefined
    throw new ApiError(response.status, problem)
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** A file from the API with the login, as a Blob (images of results and jobs). */
export async function fetchBlob(path: string): Promise<Blob> {
  const { token } = useSession.getState()
  const response = await fetch(`${location.origin}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    if (response.status === 401 && token) useSession.getState().expire()
    throw new ApiError(
      response.status,
      (await response.json().catch(() => undefined)) as Partial<Problem> | undefined,
    )
  }
  return response.blob()
}
