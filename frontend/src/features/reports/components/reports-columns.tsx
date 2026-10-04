import { type ColumnDef } from '@tanstack/react-table'
import { Flame, Hourglass, Smartphone } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { DataTableColumnHeader } from '@/components/data-table'
import { cn } from '@/lib/utils'
import {
  formatDateTime,
  formatDuration,
  reportDurationS,
  reportKind,
  type LeanLensReport,
  type ReportKind,
} from '@/lib/leanlens-api'

const KIND_META: Record<
  ReportKind,
  { label: string; icon: React.ElementType; className: string }
> = {
  smartphone: {
    label: 'Smartphone',
    icon: Smartphone,
    className: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30',
  },
  idle: {
    label: 'Idle',
    icon: Hourglass,
    className:
      'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30',
  },
  other: {
    label: 'Event',
    icon: Flame,
    className: 'bg-muted text-muted-foreground border-border',
  },
}

export const reportKindMeta = KIND_META

export const reportsColumns: ColumnDef<LeanLensReport>[] = [
  {
    id: 'kind',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Type' />
    ),
    accessorFn: (row) => reportKind(row),
    cell: ({ row }) => {
      const kind = reportKind(row.original)
      const meta = KIND_META[kind]
      return (
        <div className='flex items-center gap-2 ps-3'>
          <Badge variant='outline' className={cn('gap-1.5', meta.className)}>
            <meta.icon className='size-3' />
            {meta.label}
          </Badge>
        </div>
      )
    },
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
    enableHiding: false,
  },
  {
    id: 'camera',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Camera' />
    ),
    accessorFn: (row) => row.camera?.name ?? row.camera?.id ?? '—',
    cell: ({ row }) => (
      <div className='min-w-0'>
        <p className='truncate text-sm font-medium'>
          {row.original.camera?.name ?? '—'}
        </p>
        <p className='font-mono text-xs text-muted-foreground'>
          {row.original.camera?.id}
        </p>
      </div>
    ),
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
  },
  {
    id: 'algorithm',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Algorithm' />
    ),
    accessorFn: (row) => row.algorithm?.name ?? '—',
    cell: ({ row }) => (
      <span className='text-sm text-muted-foreground'>
        {row.original.algorithm?.name ?? '—'}
      </span>
    ),
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
  },
  {
    accessorKey: 'date_created',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Started' />
    ),
    cell: ({ row }) => (
      <span className='whitespace-nowrap text-sm'>
        {formatDateTime(row.original.start_tracking ?? row.original.date_created)}
      </span>
    ),
  },
  {
    id: 'duration',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Duration' />
    ),
    accessorFn: (row) => reportDurationS(row) ?? -1,
    cell: ({ row }) => (
      <span className='whitespace-nowrap text-sm'>
        {formatDuration(reportDurationS(row.original))}
      </span>
    ),
  },
  {
    id: 'evidence',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Evidence' />
    ),
    accessorFn: (row) => row.photos.length,
    cell: ({ row }) => {
      const count = row.original.photos.length
      if (count === 0)
        return <span className='text-sm text-muted-foreground'>—</span>
      return (
        <div className='flex items-center gap-1.5'>
          <img
            src={
              row.original.photos[0].image.startsWith('images/')
                ? `/${row.original.photos[0].image}`
                : `/images/${row.original.camera?.id}/${row.original.photos[0].image}`
            }
            alt=''
            loading='lazy'
            className='size-8 rounded border object-cover'
          />
          <span className='text-xs text-muted-foreground'>+{count - 1}</span>
        </div>
      )
    },
    enableSorting: false,
  },
  {
    id: 'status',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Status' />
    ),
    accessorFn: (row) => (row.violation_found ? 'violation' : 'ok'),
    cell: ({ row }) =>
      row.original.violation_found ? (
        <Badge variant='destructive' className='gap-1'>
          <span className='size-1.5 rounded-full bg-current' />
          Violation
        </Badge>
      ) : (
        <Badge
          variant='outline'
          className='gap-1 border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
        >
          <span className='size-1.5 rounded-full bg-current' />
          Normal
        </Badge>
      ),
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
    enableHiding: false,
  },
]
