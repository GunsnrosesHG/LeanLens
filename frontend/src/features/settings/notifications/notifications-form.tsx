import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Loader2, Mail, Plus, Trash2 } from 'lucide-react'
import { apiErrorMessage } from '@/lib/api'
import {
  createMailerEmail,
  deleteMailerEmail,
  saveSmtpSettings,
  saveWorkingTime,
  updateMailerEmail,
  useMailerEmails,
  useSmtpSettings,
  useWorkingTime,
} from '@/lib/leanlens-api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'

const ALL_DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const

function hhmm(value: string | undefined): string {
  return (value ?? '').slice(0, 5)
}

function EmailsSection() {
  const emails = useMailerEmails()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['mailer', 'emails'] })

  const createMutation = useMutation({
    mutationFn: () => createMailerEmail(draft.trim()),
    onSuccess: () => {
      toast.success('Notification email added.')
      setDraft('')
      invalidate()
    },
    onError: (error) =>
      toast.error('Could not add the email', {
        description: apiErrorMessage(error),
      }),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      updateMailerEmail(id, { is_active }),
    onSuccess: invalidate,
    onError: (error) =>
      toast.error('Could not update the email', {
        description: apiErrorMessage(error),
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteMailerEmail(id),
    onSuccess: () => {
      toast.success('Notification email removed.')
      invalidate()
    },
    onError: (error) =>
      toast.error('Could not remove the email', {
        description: apiErrorMessage(error),
      }),
  })

  return (
    <div className='space-y-4'>
      <div className='flex items-center gap-2'>
        <Mail className='size-4 text-muted-foreground' />
        <p className='text-sm font-medium'>Notification recipients</p>
      </div>
      {emails.isLoading ? (
        <Skeleton className='h-10 w-full' />
      ) : emails.error ? (
        <p className='text-sm text-destructive'>
          {apiErrorMessage(emails.error, 'Could not load recipients.')}
        </p>
      ) : (
        <ul className='space-y-2'>
          {(emails.data ?? []).map((item) => (
            <li
              key={item.id}
              className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2'
            >
              <span className='min-w-0 truncate text-sm'>{item.email}</span>
              <div className='flex shrink-0 items-center gap-3'>
                <Badge
                  variant='outline'
                  className={
                    item.is_active
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                      : 'text-muted-foreground'
                  }
                >
                  {item.is_active ? 'Active' : 'Paused'}
                </Badge>
                <Switch
                  checked={item.is_active}
                  disabled={toggleMutation.isPending}
                  onCheckedChange={(next) =>
                    toggleMutation.mutate({ id: item.id, is_active: next })
                  }
                  aria-label={`Toggle ${item.email}`}
                />
                <Button
                  variant='ghost'
                  size='icon'
                  className='size-8 text-muted-foreground hover:text-destructive'
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(item.id)}
                  aria-label={`Remove ${item.email}`}
                >
                  <Trash2 className='size-4' />
                </Button>
              </div>
            </li>
          ))}
          {(emails.data ?? []).length === 0 && (
            <li className='rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground'>
              No recipients yet — violation emails are disabled.
            </li>
          )}
        </ul>
      )}
      <form
        className='flex gap-2'
        onSubmit={(e) => {
          e.preventDefault()
          if (draft.trim()) createMutation.mutate()
        }}
      >
        <Input
          type='email'
          required
          placeholder='supervisor@company.com'
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <Button type='submit' variant='outline' disabled={createMutation.isPending}>
          {createMutation.isPending ? (
            <Loader2 className='size-4 animate-spin' />
          ) : (
            <Plus className='size-4' />
          )}
          Add
        </Button>
      </form>
    </div>
  )
}

function WorkingTimeSection() {
  const workingTime = useWorkingTime()

  if (workingTime.isLoading) return <Skeleton className='h-24 w-full' />
  if (workingTime.error)
    return (
      <p className='text-sm text-destructive'>
        {apiErrorMessage(workingTime.error, 'Could not load the working time.')}
      </p>
    )

  // key = remise à zéro de l'état local uniquement quand l'ID serveur change
  // (premier chargement) — évite un useEffect de synchronisation
  // (react-hooks/set-state-in-effect) tout en conservant les éditions locales
  // entre deux refetchs du même enregistrement.
  return (
    <WorkingTimeEditor
      key={workingTime.data?.id ?? 'empty'}
      initial={{
        start: hhmm(workingTime.data?.time_start) || '09:00',
        end: hhmm(workingTime.data?.time_end) || '18:00',
        days:
          workingTime.data?.days_of_week?.map((d) => d.day) ?? [
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
          ],
      }}
    />
  )
}

function WorkingTimeEditor({
  initial,
}: {
  initial: { start: string; end: string; days: string[] }
}) {
  const queryClient = useQueryClient()
  const [start, setStart] = useState(initial.start)
  const [end, setEnd] = useState(initial.end)
  const [days, setDays] = useState<string[]>(initial.days)

  const mutation = useMutation({
    mutationFn: () => saveWorkingTime(start, end, days),
    onSuccess: () => {
      toast.success('Working time saved — alerts outside this window are silenced.')
      queryClient.invalidateQueries({ queryKey: ['mailer', 'working-time'] })
    },
    onError: (error) =>
      toast.error('Could not save the working time', {
        description: apiErrorMessage(error),
      }),
  })

  const toggleDay = (day: string) =>
    setDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )

  return (
    <div className='space-y-4'>
      <p className='text-sm font-medium'>Working time</p>
      <p className='text-sm text-muted-foreground'>
        Violation notifications are only sent during these hours.
      </p>
      <div className='flex flex-wrap items-center gap-4'>
        <div className='flex items-center gap-2'>
          <Label htmlFor='work-start' className='text-sm text-muted-foreground'>
            From
          </Label>
          <Input
            id='work-start'
            type='time'
            className='w-32'
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className='flex items-center gap-2'>
          <Label htmlFor='work-end' className='text-sm text-muted-foreground'>
            To
          </Label>
          <Input
            id='work-end'
            type='time'
            className='w-32'
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
      </div>
      <div className='flex flex-wrap gap-4'>
        {ALL_DAYS.map((day) => (
          <label key={day} className='flex items-center gap-2 text-sm'>
            <Checkbox
              checked={days.includes(day)}
              onCheckedChange={() => toggleDay(day)}
            />
            {day.slice(0, 3)}
          </label>
        ))}
      </div>
      <Button
        type='button'
        variant='outline'
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? (
          <>
            <Loader2 className='me-2 size-4 animate-spin' /> Saving…
          </>
        ) : (
          'Save working time'
        )}
      </Button>
    </div>
  )
}

function SmtpSection() {
  const smtp = useSmtpSettings()

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between gap-2'>
        <p className='text-sm font-medium'>SMTP server</p>
        <Badge variant='outline' className='text-muted-foreground'>
          {smtp.data ? 'configured' : 'not configured'}
        </Badge>
      </div>
      <p className='text-sm text-muted-foreground'>
        Required to send violation emails. The server tests the connection when
        you save — wrong credentials are rejected.
      </p>
      {smtp.isLoading ? (
        <Skeleton className='h-10 w-full' />
      ) : smtp.error ? (
        <p className='text-sm text-destructive'>
          {apiErrorMessage(smtp.error, 'Could not load SMTP settings.')}
        </p>
      ) : (
        // key = réinitialisation locale uniquement quand l'ID serveur change
        // (même principe que WorkingTimeEditor — pas de synchronisation via
        // useEffect). Le mot de passe n'est jamais pré-rempli depuis l'API.
        <SmtpEditor
          key={smtp.data?.id ?? 'empty'}
          smtpId={smtp.data?.id}
          initial={{
            server: smtp.data?.server ?? '',
            port: String(smtp.data?.port ?? 587),
            username: smtp.data?.username ?? '',
            useTls: smtp.data?.email_use_tls ?? false,
            useSsl: smtp.data?.email_use_ssl ?? true,
          }}
        />
      )}
    </div>
  )
}

function SmtpEditor({
  smtpId,
  initial,
}: {
  smtpId: number | undefined
  initial: {
    server: string
    port: string
    username: string
    useTls: boolean
    useSsl: boolean
  }
}) {
  const queryClient = useQueryClient()
  const [server, setServer] = useState(initial.server)
  const [port, setPort] = useState(initial.port)
  const [username, setUsername] = useState(initial.username)
  const [password, setPassword] = useState('')
  const [useTls, setUseTls] = useState(initial.useTls)
  const [useSsl, setUseSsl] = useState(initial.useSsl)

  const mutation = useMutation({
    mutationFn: () =>
      saveSmtpSettings({
        id: smtpId,
        server,
        port: Number(port) || 587,
        username,
        password,
        email_use_tls: useTls,
        email_use_ssl: useSsl,
      }),
    onSuccess: () => {
      toast.success('SMTP settings saved (connection validated by the server).')
      setPassword('')
      queryClient.invalidateQueries({ queryKey: ['mailer', 'smtp'] })
    },
    onError: (error) =>
      toast.error('Could not save the SMTP settings', {
        description: `${apiErrorMessage(error)} — the server validates the connection on save.`,
      }),
  })

  return (
    <>
      <div className='grid gap-4 sm:grid-cols-2'>
        <div className='space-y-2'>
          <Label htmlFor='smtp-server'>Server</Label>
          <Input
            id='smtp-server'
            placeholder='smtp.gmail.com'
            value={server}
            onChange={(e) => setServer(e.target.value)}
          />
        </div>
        <div className='space-y-2'>
          <Label htmlFor='smtp-port'>Port</Label>
          <Input
            id='smtp-port'
            type='number'
            value={port}
            onChange={(e) => setPort(e.target.value)}
          />
        </div>
        <div className='space-y-2'>
          <Label htmlFor='smtp-user'>Username</Label>
          <Input
            id='smtp-user'
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className='space-y-2'>
          <Label htmlFor='smtp-pass'>Password</Label>
          <Input
            id='smtp-pass'
            type='password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className='flex items-center gap-6'>
          <label className='flex items-center gap-2 text-sm'>
            <Switch checked={useTls} onCheckedChange={setUseTls} /> TLS
          </label>
          <label className='flex items-center gap-2 text-sm'>
            <Switch checked={useSsl} onCheckedChange={setUseSsl} /> SSL
          </label>
        </div>
      </div>
      <Button type='button' disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? (
          <>
            <Loader2 className='me-2 size-4 animate-spin' /> Testing & saving…
          </>
        ) : smtpId ? (
          'Update SMTP settings'
        ) : (
          'Save SMTP settings'
        )}
      </Button>
    </>
  )
}

export function NotificationsForm() {
  return (
    <div className='space-y-8'>
      <EmailsSection />
      <Separator />
      <WorkingTimeSection />
      <Separator />
      <SmtpSection />
    </div>
  )
}
