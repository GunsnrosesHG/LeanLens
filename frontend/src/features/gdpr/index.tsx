import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  EyeOff,
  FileText,
  Gavel,
  Lock,
  RefreshCw,
  ScanFace,
  ShieldCheck,
} from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { apiErrorMessage } from '@/lib/api'
import { useCompany, useGdprStatus } from '@/lib/leanlens-api'
import { cn } from '@/lib/utils'

// ---------- live anonymisation status ----------

function StatusBadge({
  className,
  tone,
  children,
}: {
  className?: string
  tone: 'ok' | 'warn' | 'off'
  children: React.ReactNode
}) {
  return (
    <Badge
      variant='outline'
      className={cn(
        'gap-1.5 px-2.5 py-1',
        tone === 'ok' &&
          'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
        tone === 'warn' &&
          'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
        tone === 'off' &&
          'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400',
        className
      )}
    >
      <span className='size-1.5 rounded-full bg-current' />
      {children}
    </Badge>
  )
}

function AnonymisationCard() {
  const status = useGdprStatus()
  const queryClient = useQueryClient()

  const body = () => {
    if (status.isLoading)
      return (
        <p className='text-sm text-muted-foreground'>
          Checking worker heartbeat…
        </p>
      )
    if (status.error)
      return (
        <div className='space-y-2'>
          <StatusBadge tone='warn'>Status unavailable</StatusBadge>
          <p className='text-sm text-muted-foreground'>
            {apiErrorMessage(status.error, 'The Django API did not respond.')}
          </p>
        </div>
      )
    const data = status.data
    if (!data)
      return (
        <p className='text-sm text-muted-foreground'>No status reported yet.</p>
      )
    if (!data.reported || (data.stale && !data.blur_active))
      return (
        <div className='space-y-2'>
          <StatusBadge tone='warn'>
            {data.stale ? 'Worker heartbeat stale' : 'No worker report yet'}
          </StatusBadge>
          <p className='text-sm text-muted-foreground'>
            The detection worker has not reported its privacy configuration
            recently. Evidence generation may be stopped (algorithm disabled or
            worker offline).
          </p>
        </div>
      )
    return (
      <div className='space-y-2'>
        <div className='flex flex-wrap items-center gap-2'>
          <StatusBadge tone={data.blur_active ? 'ok' : 'off'}>
            {data.blur_active
              ? `Face blurring active — ${data.blur_mode}`
              : 'Face blurring DISABLED'}
          </StatusBadge>
          {data.stale ? <StatusBadge tone='warn'>stale</StatusBadge> : null}
        </div>
        <p className='text-sm text-muted-foreground'>
          Reported by the detection worker
          {data.algorithm ? ` (${data.algorithm})` : ''}
          {data.camera ? ` on ${data.camera}` : ''}
          {data.age_seconds != null
            ? ` — ${data.age_seconds < 90
                ? `${data.age_seconds}s ago`
                : `${Math.round(data.age_seconds / 60)} min ago`}`
            : ''}
          .
        </p>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className='pb-2'>
        <div className='flex items-center justify-between gap-2'>
          <div className='flex items-center gap-2'>
            <ScanFace className='size-5 text-muted-foreground' />
            <CardTitle className='text-base'>Live anonymisation status</CardTitle>
          </div>
          <Button
            variant='ghost'
            size='icon'
            className='size-8'
            aria-label='Refresh status'
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['gdpr-status'] })
              toast.success('Status refreshed.')
            }}
          >
            <RefreshCw className='size-4' />
          </Button>
        </div>
        <CardDescription>
          Reported directly by the detection worker — not a static setting.
        </CardDescription>
      </CardHeader>
      <CardContent>{body()}</CardContent>
    </Card>
  )
}

// ---------- policy sections ----------

function Policy() {
  const company = useCompany()
  const contact = company.data?.contact_email || 'contact@leanlens.fr'

  return (
    <div className='grid gap-4 lg:grid-cols-2'>
      <Card>
        <CardHeader className='pb-2'>
          <div className='flex items-center gap-2'>
            <FileText className='size-5 text-muted-foreground' />
            <CardTitle className='text-base'>Data collected</CardTitle>
          </div>
        </CardHeader>
        <CardContent className='space-y-2 text-sm text-muted-foreground'>
          <p>
            LeanLens processes image streams from the cameras registered on the
            platform for the sole purpose of workplace-safety detection
            (smartphone usage and prolonged idleness).
          </p>
          <ul className='list-disc space-y-1 ps-5'>
            <li>
              <span className='font-medium text-foreground'>
                Evidence photos
              </span>{' '}
              — captured only when a violation is detected, stored under{' '}
              <code className='font-mono text-xs'>/images/&lt;camera&gt;/</code>.
            </li>
            <li>
              <span className='font-medium text-foreground'>
                Detection metadata
              </span>{' '}
              — timestamps, camera, algorithm, duration of the violation.
            </li>
          </ul>
          <p>
            No biometric identification is performed: faces are never used to
            identify or re-identify individuals.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className='pb-2'>
          <div className='flex items-center gap-2'>
            <EyeOff className='size-5 text-muted-foreground' />
            <CardTitle className='text-base'>Anonymisation by design</CardTitle>
          </div>
        </CardHeader>
        <CardContent className='space-y-2 text-sm text-muted-foreground'>
          <p>
            Faces detected in evidence photos are anonymised{' '}
            <span className='font-medium text-foreground'>
              before the photo leaves the detection worker
            </span>{' '}
            — the stored and shared image is already blurred. The analysis
            frames themselves are never persisted.
          </p>
          <p>
            The blur pipeline (OpenCV Haar cascade) supports three modes —
            pixelate (default), gaussian blur, or solid patch — configured per
            deployment and reported live in the status card above.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className='pb-2'>
          <div className='flex items-center gap-2'>
            <Lock className='size-5 text-muted-foreground' />
            <CardTitle className='text-base'>Retention & minimisation</CardTitle>
          </div>
        </CardHeader>
        <CardContent className='space-y-2 text-sm text-muted-foreground'>
          <p>
            Evidence photos are kept solely as long as needed to demonstrate and
            review detected violations; deletion of a camera removes its
            assignment links immediately. Only the latest reports are exposed in
            the UI, and every photo is bound to its violation record.
          </p>
          <p>
            Access to the platform requires an authenticated account; user
            accounts are provisioned by administrators only (no self
            registration).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className='pb-2'>
          <div className='flex items-center gap-2'>
            <Gavel className='size-5 text-muted-foreground' />
            <CardTitle className='text-base'>Your rights</CardTitle>
          </div>
        </CardHeader>
        <CardContent className='space-y-2 text-sm text-muted-foreground'>
          <p>
            In accordance with the GDPR, individuals may request access to,
            rectification or deletion of data concerning them, and may object to
            processing. Requests are handled by the data controller:
          </p>
          <p className='font-medium text-foreground'>{contact}</p>
          <p>
            To exercise a right about a specific violation, provide the report
            identifier shown in the Reports page.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

// ---------- page ----------

export function Gdpr() {
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
          <h2 className='flex items-center gap-2 text-2xl font-bold tracking-tight'>
            <ShieldCheck className='size-6' /> GDPR & privacy
          </h2>
          <p className='text-muted-foreground'>
            How LeanLens protects the people it monitors — live anonymisation
            status and data-protection policy.
          </p>
        </div>

        <AnonymisationCard />
        <Policy />
      </Main>
    </>
  )
}
