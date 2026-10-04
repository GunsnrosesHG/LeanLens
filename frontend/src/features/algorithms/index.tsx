import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Video, Workflow } from 'lucide-react'
import { apiErrorMessage } from '@/lib/api'
import {
  toggleAlgorithm,
  useAlgorithms,
  useCamerasWithAlgorithms,
  type AlgorithmDetail,
  type CameraWithAlgorithms,
} from '@/lib/leanlens-api'

function AlgorithmRow({
  cameraIp,
  algorithm,
  enabled,
  disabled,
  onToggle,
  busy,
}: {
  cameraIp: string
  algorithm: AlgorithmDetail
  enabled: boolean
  disabled: boolean
  onToggle: (cameraIp: string, algorithmName: string, next: boolean) => void
  busy: boolean
}) {
  return (
    <div
      key={algorithm.id}
      className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5'
    >
      <div className='flex min-w-0 flex-col'>
        <span className='truncate font-mono text-sm'>{algorithm.name}</span>
        {algorithm.description ? (
          <span className='truncate text-xs text-muted-foreground'>
            {algorithm.description}
          </span>
        ) : null}
      </div>
      <div className='flex shrink-0 items-center gap-2'>
        <Badge
          variant='outline'
          className={
            enabled
              ? 'gap-1 border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              : 'gap-1 text-muted-foreground'
          }
        >
          <span className='size-1.5 rounded-full bg-current' />
          {enabled ? 'Active' : 'Off'}
        </Badge>
        <Switch
          checked={enabled}
          disabled={disabled || busy}
          onCheckedChange={(next) => onToggle(cameraIp, algorithm.name, next)}
          aria-label={`${enabled ? 'Disable' : 'Enable'} ${algorithm.name} on ${cameraIp}`}
        />
      </div>
    </div>
  )
}

export function Algorithms() {
  const queryClient = useQueryClient()
  const cameras = useCamerasWithAlgorithms()
  const algorithms = useAlgorithms()
  const [pending, setPending] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({
      cameraIp,
      algorithmName,
      next,
    }: {
      cameraIp: string
      algorithmName: string
      next: boolean
    }) => toggleAlgorithm(cameraIp, algorithmName, next),
    onSuccess: (_data, variables) => {
      toast.success(
        `${variables.algorithmName} ${variables.next ? 'enabled' : 'disabled'} on ${variables.cameraIp}`,
        {
          description: variables.next
            ? 'The detection worker resumes within a few seconds.'
            : 'The detection worker suspends within a few seconds.',
        }
      )
    },
    onError: (error, variables) => {
      toast.error(
        `Could not ${variables.next ? 'enable' : 'disable'} ${variables.algorithmName}`,
        { description: apiErrorMessage(error) }
      )
    },
    onSettled: () => {
      setPending(null)
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
  })

  const handleToggle = (
    cameraIp: string,
    algorithmName: string,
    next: boolean
  ) => {
    setPending(`${cameraIp}:${algorithmName}`)
    mutation.mutate({ cameraIp, algorithmName, next })
  }

  const list: CameraWithAlgorithms[] = cameras.data ?? []
  const loading = cameras.isLoading || algorithms.isLoading
  const error = cameras.error ?? algorithms.error
  const available: AlgorithmDetail[] = (algorithms.data ?? []).filter(
    (a) => a.is_available
  )

  const linkFor = (camera: CameraWithAlgorithms, name: string) =>
    camera.algorithms?.find((l) => l.algorithm.name === name && l.is_active)

  return (
    <>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>Algorithms</h2>
          <p className='text-muted-foreground'>
            Enable or disable detection algorithms for each camera. Disabling
            suspends the worker within seconds — reports stop immediately.
          </p>
        </div>

        {error ? (
          <Alert variant='destructive'>
            <AlertTitle>Could not load assignments</AlertTitle>
            <AlertDescription>
              {apiErrorMessage(error, 'The Django API did not respond.')}
            </AlertDescription>
          </Alert>
        ) : loading ? (
          <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-3'>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className='h-52 rounded-xl' />
            ))}
          </div>
        ) : list.length === 0 ? (
          <div className='flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center'>
            <Video className='size-8 text-muted-foreground' />
            <p className='font-medium'>No cameras yet</p>
            <p className='max-w-sm text-sm text-muted-foreground'>
              Add cameras first — algorithms are assigned per camera.
            </p>
          </div>
        ) : (
          <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-3'>
            {list.map((camera) => (
              <Card key={camera.id} className='gap-4'>
                <CardHeader className='pb-0'>
                  <div className='flex items-start justify-between gap-2'>
                    <div className='flex items-center gap-2'>
                      <div className='flex size-10 items-center justify-center rounded-lg bg-muted'>
                        <Video className='size-5 text-muted-foreground' />
                      </div>
                      <div className='min-w-0'>
                        <CardTitle className='truncate'>
                          {camera.name}
                        </CardTitle>
                        <CardDescription className='font-mono'>
                          {camera.id}
                        </CardDescription>
                      </div>
                    </div>
                    <Badge
                      variant='outline'
                      className={
                        camera.is_active
                          ? 'shrink-0 border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'shrink-0 border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400'
                      }
                    >
                      <span className='size-1.5 rounded-full bg-current' />
                      {camera.is_active ? 'Online' : 'Offline'}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className='flex flex-col gap-2'>
                  {available.length ? (
                    available.map((algorithm) => {
                      const key = `${camera.id}:${algorithm.name}`
                      const enabled = Boolean(linkFor(camera, algorithm.name))
                      return (
                        <AlgorithmRow
                          key={algorithm.id}
                          cameraIp={camera.id}
                          algorithm={algorithm}
                          enabled={enabled}
                          disabled={!camera.is_active}
                          busy={
                            mutation.isPending &&
                            pending === key
                          }
                          onToggle={handleToggle}
                        />
                      )
                    })
                  ) : (
                    <p className='flex items-center gap-2 rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground'>
                      <Workflow className='size-4' />
                      No algorithm available for assignment.
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Main>
    </>
  )
}
