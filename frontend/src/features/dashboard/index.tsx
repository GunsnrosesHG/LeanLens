import { useMemo } from 'react'
import { Link } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  Cpu,
  Eye,
  Monitor,
  RefreshCcw,
  Smartphone,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { ConfigDrawer } from '@/components/config-drawer'
import {
  formatDateTime,
  photoUrl,
  reportKind,
  useCameras,
  useHealthcheck,
  useReports,
  type LeanLensReport,
} from '@/lib/leanlens-api'
import { ReportsPerDay } from './components/reports-per-day'
import { cn } from '@/lib/utils'

const KIND_LABEL: Record<string, string> = {
  smartphone: 'Smartphone usage',
  idle: 'Idle detected',
  other: 'Event',
}

export function Dashboard() {
  const reports = useReports()
  const health = useHealthcheck()
  const cameras = useCameras()
  const queryClient = useQueryClient()

  const allReports = reports.data?.reports ?? []

  const kpis = useMemo(() => {
    const violations = allReports.filter((r) => r.violation_found).length
    const phone = allReports.filter((r) => reportKind(r) === 'smartphone').length
    const idle = allReports.filter((r) => reportKind(r) === 'idle').length
    return {
      total: reports.data?.count ?? allReports.length,
      violations,
      phone,
      idle,
    }
  }, [allReports, reports.data?.count])

  const recent = useMemo(
    () =>
      [...allReports]
        .sort((a, b) => (b.date_created ?? '').localeCompare(a.date_created ?? ''))
        .slice(0, 6),
    [allReports]
  )

  const camerasOnline = health.data?.devices?.count ?? cameras.data?.length ?? 0

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['reports'] }),
      queryClient.invalidateQueries({ queryKey: ['healthcheck'] }),
      queryClient.invalidateQueries({ queryKey: ['cameras'] }),
    ])
    toast.success('Dashboard refreshed')
  }

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
            <h2 className='text-2xl font-bold tracking-tight'>Dashboard</h2>
            <p className='text-muted-foreground'>
              Live overview of workplace monitoring across your cameras.
            </p>
          </div>
          <div className='flex items-center gap-2'>
            <Button variant='outline' size='sm' onClick={refresh}>
              <RefreshCcw /> Refresh
            </Button>
            <Button size='sm' asChild>
              <Link to='/reports'>
                View reports <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>

        {/* KPI cards */}
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
          <KpiCard
            title='Total reports'
            value={kpis.total}
            hint='sent by the algorithm container'
            loading={reports.isLoading}
            icon={<Eye className='size-4 text-muted-foreground' />}
          />
          <KpiCard
            title='Violations'
            value={kpis.violations}
            hint='confirmed by the detector'
            loading={reports.isLoading}
            icon={<Smartphone className='size-4 text-muted-foreground' />}
            accent='text-red-500'
          />
          <KpiCard
            title='Cameras online'
            value={camerasOnline}
            hint='discovered devices'
            loading={health.isLoading || cameras.isLoading}
            icon={<Monitor className='size-4 text-muted-foreground' />}
            accent='text-emerald-500'
          />
          <KpiCard
            title='CPU load'
            value={health.data ? `${Math.round(health.data.cpu_load)}%` : null}
            hint='platform host'
            loading={health.isLoading}
            icon={<Cpu className='size-4 text-muted-foreground' />}
          />
        </div>

        {/* Chart + recent violations */}
        <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
          <Card className='col-span-1 lg:col-span-4'>
            <CardHeader>
              <CardTitle>Reports per day</CardTitle>
              <CardDescription>
                Smartphone usage vs. idle alerts — last 7 days
              </CardDescription>
            </CardHeader>
            <CardContent className='ps-2'>
              <ReportsPerDay reports={allReports} loading={reports.isLoading} />
            </CardContent>
          </Card>

          <Card className='col-span-1 lg:col-span-3'>
            <CardHeader className='flex flex-row items-center justify-between'>
              <div className='space-y-1.5'>
                <CardTitle>Recent reports</CardTitle>
                <CardDescription>Latest events from all cameras</CardDescription>
              </div>
              <Link
                to='/reports'
                className='flex items-center text-sm text-muted-foreground hover:text-foreground'
              >
                All <ArrowRight className='size-4' />
              </Link>
            </CardHeader>
            <CardContent className='flex flex-col gap-4'>
              {reports.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className='flex items-center gap-3'>
                    <Skeleton className='size-11 rounded-md' />
                    <div className='flex-1 space-y-2'>
                      <Skeleton className='h-3.5 w-2/3' />
                      <Skeleton className='h-3 w-1/3' />
                    </div>
                  </div>
                ))
              ) : recent.length === 0 ? (
                <p className='py-6 text-center text-sm text-muted-foreground'>
                  No reports yet — run the demo scenario to see live events.
                </p>
              ) : (
                recent.map((report) => (
                  <RecentReportRow key={report.id} report={report} />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
}

function KpiCard({
  title,
  value,
  hint,
  icon,
  loading,
  accent,
}: {
  title: string
  value: number | string | null
  hint: string
  icon: React.ReactNode
  loading?: boolean
  accent?: string
}) {
  return (
    <Card>
      <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
        <CardTitle className='text-sm font-medium'>{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        {loading || value == null ? (
          <Skeleton className='h-8 w-20' />
        ) : (
          <div className={cn('text-2xl font-bold', accent)}>{value}</div>
        )}
        <p className='text-xs text-muted-foreground'>{hint}</p>
      </CardContent>
    </Card>
  )
}

function RecentReportRow({ report }: { report: LeanLensReport }) {
  const kind = reportKind(report)
  const photo = report.photos[0]
  return (
    <Link
      to='/reports'
      className='flex items-center gap-3 rounded-lg p-1 transition-colors hover:bg-accent'
    >
      {photo ? (
        <img
          src={photoUrl(photo, report.camera.id)}
          alt=''
          loading='lazy'
          className='size-11 rounded-md border object-cover'
        />
      ) : (
        <div className='flex size-11 items-center justify-center rounded-md border bg-muted'>
          <Smartphone className='size-4 text-muted-foreground' />
        </div>
      )}
      <div className='min-w-0 flex-1'>
        <p className='truncate text-sm font-medium'>
          {KIND_LABEL[kind] ?? kind}
        </p>
        <p className='truncate text-xs text-muted-foreground'>
          {report.camera.name} · {formatDateTime(report.date_created)}
        </p>
      </div>
      <span
        className={cn(
          'size-2 shrink-0 rounded-full',
          report.violation_found ? 'bg-red-500' : 'bg-emerald-500'
        )}
        title={report.violation_found ? 'Violation' : 'Normal activity'}
      />
    </Link>
  )
}
