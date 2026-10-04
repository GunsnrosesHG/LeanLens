import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import {
  Camera as CameraIcon,
  Loader2,
  Radar,
  Trash2,
  Video,
} from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/lib/api'
import {
  createCamera,
  deleteCamera,
  discoverCameras,
  useCameras,
  useCamerasWithAlgorithms,
  type CameraWithAlgorithms,
  type DiscoveredCamera,
} from '@/lib/leanlens-api'
import { cn } from '@/lib/utils'

// ---------- add dialog ----------

const addCameraSchema = z.object({
  ip: z.string().regex(/^\d{1,3}(\.\d{1,3}){3}$/, 'A valid IPv4 address is required.'),
  name: z.string().max(100, 'At most 100 characters.').optional(),
  username: z.string().max(100, 'At most 100 characters.').optional(),
  password: z.string().max(100, 'At most 100 characters.').optional(),
})

type AddCameraValues = z.infer<typeof addCameraSchema>

function AddCameraDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [scanState, setScanState] = useState<
    { status: 'idle' } | { status: 'scanning' } | { status: 'done'; found: DiscoveredCamera[] } | { status: 'error'; message: string }
  >({ status: 'idle' })

  const form = useForm<AddCameraValues>({
    resolver: zodResolver(addCameraSchema),
    defaultValues: { ip: '', name: '', username: '', password: '' },
  })

  const mutation = useMutation({
    mutationFn: createCamera,
    onSuccess: (camera) => {
      toast.success(`Camera "${camera.id}" added.`)
      form.reset()
      setScanState({ status: 'idle' })
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
    onError: (error) => {
      toast.error('Could not add the camera', {
        description: apiErrorMessage(error),
      })
    },
  })

  const scan = useMutation({
    mutationFn: discoverCameras,
    onSuccess: (found) => setScanState({ status: 'done', found }),
    onError: () =>
      setScanState({
        status: 'error',
        message:
          'Discovery service is not available in this deployment — enter the camera address manually.',
      }),
  })

  const prefill = (camera: DiscoveredCamera) => {
    form.setValue('ip', camera.ip)
    if (camera.name) form.setValue('name', camera.name)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          form.reset()
          setScanState({ status: 'idle' })
        }
        onOpenChange(next)
      }}
    >
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Add camera</DialogTitle>
          <DialogDescription>
            Register a network camera. Assign algorithms to it afterwards from
            the Algorithms page.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            id='add-camera-form'
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            className='space-y-4'
          >
            <FormField
              control={form.control}
              name='ip'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Camera address (IP)</FormLabel>
                  <FormControl>
                    <Input placeholder='192.168.1.64' {...field} />
                  </FormControl>
                  <FormDescription>
                    The camera's IP on the monitoring network.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='name'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display name</FormLabel>
                  <FormControl>
                    <Input placeholder='Atelier — ligne 1' {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className='grid grid-cols-2 gap-3'>
              <FormField
                control={form.control}
                name='username'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Username</FormLabel>
                    <FormControl>
                      <Input
                        placeholder='onvif user'
                        autoComplete='off'
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name='password'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type='password'
                        placeholder='••••••••'
                        autoComplete='new-password'
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </form>
        </Form>

        <div className='rounded-lg border p-3'>
          <div className='flex items-center justify-between gap-2'>
            <div>
              <p className='text-sm font-medium'>Network discovery</p>
              <p className='text-xs text-muted-foreground'>
                Scan the local network for RTSP cameras.
              </p>
            </div>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={scan.isPending}
              onClick={() => {
                setScanState({ status: 'scanning' })
                scan.mutate()
              }}
            >
              {scan.isPending ? (
                <>
                  <Loader2 className='me-2 size-4 animate-spin' /> Scanning…
                </>
              ) : (
                <>
                  <Radar className='me-2 size-4' /> Scan network
                </>
              )}
            </Button>
          </div>
          {scanState.status === 'done' && scanState.found.length > 0 && (
            <div className='mt-3 flex flex-wrap gap-2'>
              {scanState.found.map((camera) => (
                <button
                  key={camera.ip}
                  type='button'
                  onClick={() => prefill(camera)}
                  className='rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs hover:bg-muted'
                  title='Use this camera'
                >
                  {camera.ip}
                  {camera.name ? ` — ${camera.name}` : ''}
                </button>
              ))}
            </div>
          )}
          {scanState.status === 'done' && scanState.found.length === 0 && (
            <p className='mt-3 text-xs text-muted-foreground'>
              No camera found on the network — enter the address manually.
            </p>
          )}
          {scanState.status === 'error' && (
            <p className='mt-3 text-xs text-muted-foreground'>
              {scanState.message}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type='submit'
            form='add-camera-form'
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className='me-2 size-4 animate-spin' /> Adding…
              </>
            ) : (
              'Add camera'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------- page ----------

export function Cameras() {
  const cameras = useCameras()
  const processes = useCamerasWithAlgorithms()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CameraWithAlgorithms | null>(
    null
  )

  const deleteMutation = useMutation({
    mutationFn: (camera: CameraWithAlgorithms) => deleteCamera(camera.id),
    onSuccess: (_data, camera) => {
      toast.success(`Camera "${camera.id}" deleted.`)
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
    onError: (error) => {
      toast.error('Could not delete the camera', {
        description: apiErrorMessage(error),
      })
    },
  })

  const list: CameraWithAlgorithms[] =
    processes.data ??
    (cameras.data ?? []).map((c) => ({ ...c, algorithms: [] }))
  const loading = cameras.isLoading || processes.isLoading
  const error = cameras.error ?? processes.error

  return (
    <>
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-end justify-between gap-2'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>Cameras</h2>
            <p className='text-muted-foreground'>
              Discovered cameras and the algorithms assigned to each of them.
            </p>
          </div>
          <Button onClick={() => setAddOpen(true)}>
            <CameraIcon className='me-2 size-4' /> Add camera
          </Button>
        </div>

        {error ? (
          <Alert variant='destructive'>
            <AlertTitle>Could not load cameras</AlertTitle>
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
            <CameraIcon className='size-8 text-muted-foreground' />
            <p className='font-medium'>No cameras yet</p>
            <p className='max-w-sm text-sm text-muted-foreground'>
              Add a camera manually or scan the network — cameras appear here
              with their assigned algorithms.
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
                    <div className='flex shrink-0 items-center gap-1'>
                      <Badge
                        variant='outline'
                        className={cn(
                          'gap-1',
                          camera.is_active
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400'
                        )}
                      >
                        <span className='size-1.5 rounded-full bg-current' />
                        {camera.is_active ? 'Online' : 'Offline'}
                      </Badge>
                      <Button
                        variant='ghost'
                        size='icon'
                        className='size-8 text-muted-foreground hover:text-destructive'
                        onClick={() => setDeleteTarget(camera)}
                        aria-label={`Delete ${camera.id}`}
                        title='Delete camera'
                      >
                        <Trash2 className='size-4' />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className='flex flex-col gap-2'>
                  <p className='text-xs font-medium uppercase tracking-wide text-muted-foreground'>
                    Algorithms
                  </p>
                  {camera.algorithms?.length ? (
                    camera.algorithms.map((link) => (
                      <div
                        key={link.algorithm.id}
                        className='flex items-center justify-between rounded-lg border px-3 py-2'
                      >
                        <div className='flex items-center gap-2'>
                          <span className='truncate font-mono text-sm'>
                            {link.algorithm.name}
                          </span>
                        </div>
                        <Badge
                          variant='outline'
                          className={cn(
                            'gap-1',
                            link.is_active
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'text-muted-foreground'
                          )}
                        >
                          {link.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                    ))
                  ) : (
                    <p className='rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground'>
                      No algorithms assigned
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Main>

      <AddCameraDialog open={addOpen} onOpenChange={setAddOpen} />
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        destructive
        isLoading={deleteMutation.isPending}
        disabled={deleteMutation.isPending}
        handleConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
        title={`Delete camera "${deleteTarget?.id ?? ''}"?`}
        confirmText='Delete camera'
        desc={`This removes the camera and its algorithm assignments. Detection on this camera stops at the worker's next assignment poll.`}
      />
    </>
  )
}
