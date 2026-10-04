import { createFileRoute } from '@tanstack/react-router'
import { Cameras } from '@/features/cameras'

export const Route = createFileRoute('/_authenticated/cameras/')({
  component: Cameras,
})
