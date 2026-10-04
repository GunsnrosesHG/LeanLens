import { createFileRoute } from '@tanstack/react-router'
import { Gdpr } from '@/features/gdpr'

export const Route = createFileRoute('/_authenticated/gdpr/')({
  component: Gdpr,
})
