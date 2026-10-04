import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { apiErrorMessage } from '@/lib/api'
import { useReports } from '@/lib/leanlens-api'
import { ReportsTable } from './components/reports-table'

export function Reports() {
  const { data, isLoading, isError, error } = useReports()

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
          <h2 className='text-2xl font-bold tracking-tight'>Reports</h2>
          <p className='text-muted-foreground'>
            Every detection event with its GDPR-anonymized evidence photos.
          </p>
        </div>

        {isError ? (
          <Alert variant='destructive'>
            <AlertTitle>Could not load reports</AlertTitle>
            <AlertDescription>
              {apiErrorMessage(error, 'The Django API did not respond.')}
            </AlertDescription>
          </Alert>
        ) : isLoading ? (
          <div className='flex flex-1 flex-col gap-3'>
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className='h-12 w-full' />
            ))}
          </div>
        ) : (
          <ReportsTable data={data?.reports ?? []} />
        )}
      </Main>
    </>
  )
}
