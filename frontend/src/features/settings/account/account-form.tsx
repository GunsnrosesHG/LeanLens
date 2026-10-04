import { useForm } from 'react-hook-form'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { EyeIcon, EyeOffIcon, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
// FormDescription ne s'utilise QUE dans <FormField> (useFormField throw sinon)
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { apiErrorMessage } from '@/lib/api'
import { changePassword } from '@/lib/leanlens-api'
import { useAuthStore } from '@/stores/auth-store'

const passwordFormSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password.'),
    new_password: z
      .string()
      .min(8, 'At least 8 characters.')
      .regex(/[A-Z]/, 'Include an uppercase letter.')
      .regex(/[a-z]/, 'Include a lowercase letter.')
      .regex(/[0-9]/, 'Include a digit.'),
    confirm_password: z.string().min(1, 'Confirm the new password.'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match.',
    path: ['confirm_password'],
  })

type PasswordFormValues = z.infer<typeof passwordFormSchema>

export function AccountForm() {
  const user = useAuthStore((s) => s.auth.user)
  const [showPassword, setShowPassword] = useState(false)

  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordFormSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  const mutation = useMutation({
    mutationFn: (values: PasswordFormValues) =>
      changePassword(values.current_password, values.new_password),
    onSuccess: () => {
      toast.success('Password updated.')
      form.reset()
    },
    onError: (error) => {
      toast.error('Could not change the password', {
        description: apiErrorMessage(error),
      })
    },
  })

  return (
    <div className='space-y-8'>
      <div className='grid max-w-md gap-2'>
        <div className='grid grid-cols-[110px_1fr] items-center gap-2 text-sm'>
          <span className='text-muted-foreground'>Username</span>
          <span className='font-medium'>{user?.username ?? '—'}</span>
          <span className='text-muted-foreground'>Email</span>
          <span className='font-medium'>{user?.email || '—'}</span>
        </div>
        <p className='text-sm text-muted-foreground'>
          Managed by the authentication service (djoser). Use the form below to
          change your password.
        </p>
      </div>

      <Separator />

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className='max-w-md space-y-6'
        >
          <FormField
            control={form.control}
            name='current_password'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Current password</FormLabel>
                <FormControl>
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete='current-password'
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='new_password'
            render={({ field }) => (
              <FormItem>
                <FormLabel>New password</FormLabel>
                <FormControl>
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete='new-password'
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Uppercase, lowercase and a digit — validated by the server.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='confirm_password'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm new password</FormLabel>
                <FormControl>
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete='new-password'
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className='flex items-center gap-4'>
            <Button type='submit' disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className='me-2 size-4 animate-spin' /> Updating…
                </>
              ) : (
                'Change password'
              )}
            </Button>
            <button
              type='button'
              onClick={() => setShowPassword((v) => !v)}
              className='flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground'
            >
              {showPassword ? (
                <EyeOffIcon className='size-4' />
              ) : (
                <EyeIcon className='size-4' />
              )}
              {showPassword ? 'Hide' : 'Show'} passwords
            </button>
          </div>
        </form>
      </Form>
    </div>
  )
}
