import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Loader2, Trash2, UserPlus } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiErrorMessage } from '@/lib/api'
import {
  createUser,
  deleteUser,
  useUsers,
  type DjoserUser,
} from '@/lib/leanlens-api'
import { useAuthStore } from '@/stores/auth-store'

// ---------- add dialog ----------

const addUserSchema = z.object({
  username: z
    .string()
    .min(3, 'At least 3 characters.')
    .max(30, 'At most 30 characters.')
    .regex(/^[\w.@+-]+$/, 'Letters, digits and @/./+/-/_ only.'),
  // Required in practice: djoser accounts must carry a unique email
  // (the model enforces unique=True — an empty email collides with admin's).
  email: z.email('A valid, unique email is required.'),
  password: z
    .string()
    .min(8, 'At least 8 characters.')
    .regex(/[A-Z]/, 'Include an uppercase letter.')
    .regex(/[a-z]/, 'Include a lowercase letter.')
    .regex(/[0-9]/, 'Include a digit.'),
})

type AddUserValues = z.infer<typeof addUserSchema>

function AddUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const form = useForm<AddUserValues>({
    resolver: zodResolver(addUserSchema),
    defaultValues: { username: '', email: '', password: '' },
  })

  const mutation = useMutation({
    mutationFn: (values: AddUserValues) =>
      createUser(values.username, values.email, values.password),
    onSuccess: (_data, values) => {
      toast.success(`User "${values.username}" created.`)
      form.reset()
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error) => {
      toast.error('Could not create the user', {
        description: apiErrorMessage(error),
      })
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Add user</DialogTitle>
          <DialogDescription>
            Created through djoser — the account is active immediately.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            id='add-user-form'
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            className='space-y-4'
          >
            <FormField
              control={form.control}
              name='username'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Username</FormLabel>
                  <FormControl>
                    <Input placeholder='operator1' {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name='email'
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type='email' placeholder='user@leanlens.fr' {...field} />
                  </FormControl>
                  <FormDescription>
                    Must be unique — used as the account's login identifier.
                  </FormDescription>
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
                      autoComplete='new-password'
                      placeholder='••••••••'
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Uppercase, lowercase and a digit (Django validators).
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </form>
        </Form>
        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type='submit'
            form='add-user-form'
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className='me-2 size-4 animate-spin' /> Creating…
              </>
            ) : (
              'Create user'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------- delete dialog ----------

function DeleteUserDialog({
  user,
  onOpenChange,
}: {
  user: DjoserUser | null
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => deleteUser(user!.id, currentPassword),
    onSuccess: () => {
      toast.success(`User "${user!.username}" deleted.`)
      setCurrentPassword('')
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error) => {
      toast.error('Could not delete the user', {
        description: apiErrorMessage(error),
      })
    },
  })

  const open = Boolean(user)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setCurrentPassword('')
        onOpenChange(next)
      }}
    >
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Delete user "{user?.username}"?</DialogTitle>
          <DialogDescription>
            This permanently removes the account. Confirm with your own admin
            password (required by the authentication service).
          </DialogDescription>
        </DialogHeader>
        <div className='space-y-2'>
          <label
            htmlFor='delete-current-password'
            className='text-sm font-medium'
          >
            Your current password
          </label>
          <Input
            id='delete-current-password'
            type='password'
            autoComplete='current-password'
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button variant='outline' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant='destructive'
            disabled={!currentPassword || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className='me-2 size-4 animate-spin' /> Deleting…
              </>
            ) : (
              'Delete user'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------- page ----------

export function Users() {
  const users = useUsers()
  const currentUser = useAuthStore((s) => s.auth.user)
  const [addOpen, setAddOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<DjoserUser | null>(null)

  const rows = users.data ?? []

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
            <h2 className='text-2xl font-bold tracking-tight'>User List</h2>
            <p className='text-muted-foreground'>
              Platform accounts, managed through the djoser authentication API.
            </p>
          </div>
          <Button onClick={() => setAddOpen(true)}>
            <UserPlus className='me-2 size-4' /> Add user
          </Button>
        </div>

        {users.error ? (
          <Alert variant='destructive'>
            <AlertTitle>Could not load users</AlertTitle>
            <AlertDescription>
              {apiErrorMessage(users.error, 'The Django API did not respond.')}
            </AlertDescription>
          </Alert>
        ) : users.isLoading ? (
          <div className='space-y-2'>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className='h-12 w-full' />
            ))}
          </div>
        ) : (
          <div className='rounded-lg border'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className='w-16'>ID</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead className='w-24 text-end'>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className='font-mono text-muted-foreground'>
                      {user.id}
                    </TableCell>
                    <TableCell className='font-medium'>
                      {user.username}
                      {currentUser?.id === user.id ? (
                        <span className='ms-2 text-xs text-muted-foreground'>
                          (you)
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className='text-muted-foreground'>
                      {user.email || '—'}
                    </TableCell>
                    <TableCell className='text-end'>
                      <Button
                        variant='ghost'
                        size='icon'
                        className='size-8 text-muted-foreground hover:text-destructive'
                        disabled={currentUser?.id === user.id}
                        onClick={() => setDeleteTarget(user)}
                        aria-label={`Delete ${user.username}`}
                        title={
                          currentUser?.id === user.id
                            ? 'You cannot delete your own account'
                            : 'Delete user'
                        }
                      >
                        <Trash2 className='size-4' />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className='py-10 text-center text-muted-foreground'
                    >
                      No users found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </Main>

      <AddUserDialog open={addOpen} onOpenChange={setAddOpen} />
      <DeleteUserDialog user={deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)} />
    </>
  )
}
