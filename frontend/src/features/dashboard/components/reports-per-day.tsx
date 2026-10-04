import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { reportKind, type LeanLensReport } from '@/lib/leanlens-api'

type DayBucket = { day: string; smartphone: number; idle: number }

function bucketReports(reports: LeanLensReport[]): DayBucket[] {
  const days: DayBucket[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - i)
    days.push({
      day: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      smartphone: 0,
      idle: 0,
    })
  }
  const index = new Map(days.map((d, i) => {
    // reverse the label to a date key
    return [i, d] as const
  }))

  for (const report of reports) {
    if (!report.date_created) continue
    const date = new Date(report.date_created.replace(' ', 'T'))
    if (Number.isNaN(date.getTime())) continue
    date.setHours(0, 0, 0, 0)
    const diff = Math.floor((Date.now() - date.getTime()) / 86_400_000)
    if (diff < 0 || diff > 6) continue
    const bucket = index.get(6 - diff)
    if (!bucket) continue
    const kind = reportKind(report)
    if (kind === 'smartphone') bucket.smartphone += 1
    else if (kind === 'idle') bucket.idle += 1
  }
  return days
}

export function ReportsPerDay({
  reports,
  loading,
}: {
  reports: LeanLensReport[]
  loading?: boolean
}) {
  const data = useMemo(() => bucketReports(reports), [reports])

  if (loading) return <Skeleton className='h-64 w-full' />

  return (
    <ResponsiveContainer width='100%' height={260}>
      <BarChart data={data} barCategoryGap='28%'>
        <CartesianGrid strokeDasharray='3 3' className='stroke-muted' vertical={false} />
        <XAxis
          dataKey='day'
          tickLine={false}
          axisLine={false}
          fontSize={12}
          tickMargin={8}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          fontSize={12}
          width={28}
        />
        <Tooltip
          cursor={{ fill: 'hsl(var(--accent) / 0.4)' }}
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey='smartphone' name='Smartphone usage' fill='#2F7BFF' radius={[4, 4, 0, 0]} />
        <Bar dataKey='idle' name='Idle alerts' fill='#F59E0B' radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
