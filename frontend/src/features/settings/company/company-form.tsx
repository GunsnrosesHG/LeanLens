import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
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
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'
import { apiErrorMessage } from '@/lib/api'
import { saveCompany, useCompany } from '@/lib/leanlens-api'

const companyFormSchema = z.object({
  name_company: z.string().min(1, 'Company name is required.'),
  contact_email: z.email('A valid contact email is required.'),
  website: z.url('Enter a valid URL (https://…)').or(z.literal('')).optional(),
  city: z.string().max(50).optional(),
  country: z.string().max(2).optional(),
  first_address: z.string().max(100).optional(),
  contact_phone: z.string().max(30).optional(),
})

type CompanyFormValues = z.infer<typeof companyFormSchema>

export function CompanyForm() {
  const company = useCompany()
  const queryClient = useQueryClient()

  const form = useForm<CompanyFormValues>({
    resolver: zodResolver(companyFormSchema),
    defaultValues: {
      name_company: '',
      contact_email: '',
      website: '',
      city: '',
      country: '',
      first_address: '',
      contact_phone: '',
    },
  })

  useEffect(() => {
    if (company.data) {
      const c = company.data
      form.reset({
        name_company: c.name_company ?? '',
        contact_email: c.contact_email ?? '',
        website: c.website ?? '',
        city: c.city ?? '',
        country: c.country ?? '',
        first_address: c.first_address ?? '',
        contact_phone: c.contact_phone ?? '',
      })
    }
  }, [company.data, form])

  const mutation = useMutation({
    mutationFn: (values: CompanyFormValues) => {
      const existing = company.data
      return saveCompany({
        id: existing?.id,
        name_company: values.name_company,
        contact_email: values.contact_email,
        website: values.website || null,
        city: values.city || null,
        country: (values.country || '').toUpperCase() || null,
        first_address: values.first_address || null,
        contact_phone: values.contact_phone || null,
      })
    },
    onSuccess: () => {
      toast.success('Company profile saved.')
      queryClient.invalidateQueries({ queryKey: ['company'] })
    },
    onError: (error) => {
      toast.error('Could not save the company profile', {
        description: apiErrorMessage(error),
      })
    },
  })

  if (company.isLoading) {
    return (
      <div className='space-y-4'>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className='h-10 w-full' />
        ))}
      </div>
    )
  }

  if (company.error) {
    return (
      <p className='text-sm text-destructive'>
        Could not load the company profile:{' '}
        {apiErrorMessage(company.error, 'API unavailable.')}
      </p>
    )
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        className='space-y-6'
      >
        <FormField
          control={form.control}
          name='name_company'
          render={({ field }) => (
            <FormItem>
              <FormLabel>Company name</FormLabel>
              <FormControl>
                <Input placeholder='LeanLens' {...field} />
              </FormControl>
              <FormDescription>
                Shown across the platform (reports, notifications).
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='contact_email'
          render={({ field }) => (
            <FormItem>
              <FormLabel>Contact email</FormLabel>
              <FormControl>
                <Input type='email' placeholder='contact@company.com' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className='grid gap-6 sm:grid-cols-2'>
          <FormField
            control={form.control}
            name='contact_phone'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Phone</FormLabel>
                <FormControl>
                  <Input placeholder='+33 …' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='website'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Website</FormLabel>
                <FormControl>
                  <Input placeholder='https://…' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='first_address'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Address</FormLabel>
                <FormControl>
                  <Input placeholder='1 rue de…' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='city'
            render={({ field }) => (
              <FormItem>
                <FormLabel>City</FormLabel>
                <FormControl>
                  <Input placeholder='Paris' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='country'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Country code</FormLabel>
                <FormControl>
                  <Input placeholder='FR' maxLength={2} {...field} />
                </FormControl>
                <FormDescription>ISO 3166-1 alpha-2 (e.g. FR).</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <Button type='submit' disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className='me-2 size-4 animate-spin' /> Saving…
            </>
          ) : company.data ? (
            'Update company'
          ) : (
            'Create company'
          )}
        </Button>
      </form>
    </Form>
  )
}
