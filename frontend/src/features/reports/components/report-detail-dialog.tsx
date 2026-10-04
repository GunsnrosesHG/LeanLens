import { ShieldCheck } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  formatDateTime,
  formatDuration,
  photoUrl,
  reportDurationS,
  reportKind,
  type LeanLensReport,
} from '@/lib/leanlens-api'
import { reportKindMeta } from './reports-columns'

export function ReportDetailDialog({
  report,
  open,
  onOpenChange,
}: {
  report: LeanLensReport | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!report) return null
  const kind = reportKind(report)
  const meta = reportKindMeta[kind]
  const duration = reportDurationS(report)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            Report #{report.id}
            <Badge variant='outline' className={`gap-1.5 ${meta.className}`}>
              <meta.icon className='size-3' />
              {meta.label}
            </Badge>
            {report.violation_found ? (
              <Badge variant='destructive'>Violation</Badge>
            ) : (
              <Badge
                variant='outline'
                className='border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              >
                Normal
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            {report.camera?.name} ({report.camera?.id}) ·{' '}
            {report.algorithm?.name}
          </DialogDescription>
        </DialogHeader>

        <div className='grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3'>
          <Meta label='Started' value={formatDateTime(report.start_tracking ?? report.date_created)} />
          <Meta label='Stopped' value={formatDateTime(report.stop_tracking ?? report.date_updated)} />
          <Meta label='Duration' value={formatDuration(duration)} />
        </div>

        <Separator />

        <div>
          <p className='mb-2 flex items-center gap-1.5 text-sm font-medium'>
            <ShieldCheck className='size-4 text-emerald-500' />
            Evidence — faces anonymized (GDPR)
          </p>
          {report.photos.length === 0 ? (
            <p className='rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground'>
              No photos attached to this report.
            </p>
          ) : (
            <div className='grid grid-cols-2 gap-3 sm:grid-cols-3'>
              {report.photos.map((photo) => (
                <figure key={photo.id} className='overflow-hidden rounded-lg border'>
                  <img
                    src={photoUrl(photo, report.camera.id)}
                    alt={`Evidence photo ${photo.id}`}
                    loading='lazy'
                    className='aspect-video w-full bg-muted object-cover'
                  />
                  <figcaption className='truncate px-2 py-1 text-[11px] text-muted-foreground'>
                    {formatDateTime(photo.date)}
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className='text-xs text-muted-foreground'>{label}</p>
      <p className='font-medium'>{value}</p>
    </div>
  )
}
