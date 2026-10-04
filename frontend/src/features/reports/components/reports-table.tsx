import { useMemo, useState } from 'react'
import {
  type ColumnFiltersState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DataTablePagination, DataTableToolbar } from '@/components/data-table'
import { type LeanLensReport } from '@/lib/leanlens-api'
import { reportsColumns } from './reports-columns'
import { ReportDetailDialog } from './report-detail-dialog'

type ReportsTableProps = {
  data: LeanLensReport[]
}

export function ReportsTable({ data }: ReportsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'date_created', desc: true },
  ])
  const [columnFilters, onColumnFiltersChange] = useState<ColumnFiltersState>([])
  const [selected, setSelected] = useState<LeanLensReport | null>(null)

  const cameraOptions = useMemo(() => {
    const unique = new Map<string, string>()
    for (const r of data) {
      if (r.camera?.id) unique.set(r.camera.id, r.camera.name ?? r.camera.id)
    }
    return [...unique.entries()].map(([value, label]) => ({ value, label }))
  }, [data])

  const algorithmOptions = useMemo(() => {
    const unique = new Set(data.map((r) => r.algorithm?.name).filter(Boolean))
    return [...unique].map((name) => ({ value: name as string, label: name as string }))
  }, [data])

  const table = useReactTable({
    data,
    columns: reportsColumns,
    state: { sorting, columnFilters },
    onColumnFiltersChange,
    onSortingChange: setSorting,
    getPaginationRowModel: getPaginationRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  })

  return (
    <div className='flex flex-1 flex-col gap-4'>
      <DataTableToolbar
        table={table}
        searchPlaceholder='Filter by camera...'
        searchKey='camera'
        filters={[
          {
            columnId: 'kind',
            title: 'Type',
            options: [
              { value: 'smartphone', label: 'Smartphone' },
              { value: 'idle', label: 'Idle' },
              { value: 'other', label: 'Other' },
            ],
          },
          {
            columnId: 'camera',
            title: 'Camera',
            options: cameraOptions,
          },
          {
            columnId: 'algorithm',
            title: 'Algorithm',
            options: algorithmOptions,
          },
          {
            columnId: 'status',
            title: 'Status',
            options: [
              { value: 'violation', label: 'Violation' },
              { value: 'ok', label: 'Normal' },
            ],
          },
        ]}
      />

      <div className='overflow-hidden rounded-lg border'>
        <Table>
          <TableHeader className='sticky top-0 z-10 bg-background'>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className='hover:bg-transparent'>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className='cursor-pointer'
                  onClick={() => setSelected(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={reportsColumns.length}
                  className='h-32 text-center text-muted-foreground'
                >
                  No reports found — run the demo scenario to generate events.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <DataTablePagination table={table} />

      <ReportDetailDialog
        report={selected}
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
      />
    </div>
  )
}
