import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { api } from '@/lib/api'

/**
 * LeanLens backend contracts (verified live against the Django API):
 * - JWT auth: `Authorization: JWT <access>` (handled by lib/api.ts)
 * - Reports: PageNumberPagination → {count, next, previous, results}
 * - Report photos: `image` is "images/<camera_ip>/<file>.jpg", served at "/images/..."
 */

// ---------- types ----------

export interface LeanLensPhoto {
  id: number
  image: string
  date: string | null
  report_id: number
}

export interface LeanLensReport {
  id: number
  algorithm: { id: number; name: string }
  camera: { id: string; name: string; username: string }
  start_tracking: string | null
  stop_tracking: string | null
  violation_found: boolean
  /** our algorithm posts a dict {"kind": "smartphone"|"idle", ...}; upstream posts lists */
  extra: Record<string, unknown> | Array<Record<string, unknown>> | null
  date_created: string | null
  date_updated: string | null
  status: string
  photos: LeanLensPhoto[]
}

export interface LeanLensCamera {
  id: string
  name: string
  username: string
  password?: string
  is_active: boolean
}

export interface CameraAlgorithmLink {
  algorithm: { id: number; name: string }
  process_id: number
  is_active: boolean
}

/** Shape returned by the bare `/camera-algorithms/get-process/` endpoint. */
interface RawCameraLink extends CameraAlgorithmLink {
  camera: { id: string; name?: string }
}

export interface CameraWithAlgorithms extends LeanLensCamera {
  algorithms: CameraAlgorithmLink[]
}

export interface Healthcheck {
  cpu_load: number
  devices: { count: number; devices: [string][] }
  nvidia_gpu: boolean
}

export type ReportKind = 'smartphone' | 'idle' | 'other'

// ----- P2: algorithms / company / mailer / users -----

export interface AlgorithmDetail {
  id: number
  name: string
  image_name: string | null
  is_available: boolean
  description: string | null
  download_status: boolean
  used_in: string
}

export interface CompanyInfo {
  id: number
  name_company: string
  first_address?: string | null
  second_address?: string | null
  country?: string | null
  state?: string | null
  city?: string | null
  website?: string | null
  contact_email: string
  contact_phone?: string | null
  contact_mobile_phone?: string | null
  index?: number | null
}

export interface MailerEmail {
  id: number
  email: string
  is_active: boolean
}

export interface WorkingTime {
  id: number
  time_start: string // "09:00:00"
  time_end: string
  days_of_week: { id: number; day: string }[]
}

export interface SmtpSettings {
  id: number
  server: string
  port: number
  username: string
  password?: string
  email_use_tls: boolean
  email_use_ssl: boolean
}

export interface DjoserUser {
  id: number
  username: string
  email: string
}

// ---------- helpers ----------

export function reportKind(report: LeanLensReport): ReportKind {
  const extras = Array.isArray(report.extra) ? report.extra : [report.extra]
  for (const item of extras) {
    const kind = item && typeof item === 'object' ? item['kind'] : undefined
    if (kind === 'smartphone') return 'smartphone'
    if (kind === 'idle') return 'idle'
  }
  return 'other'
}

export function reportDurationS(report: LeanLensReport): number | null {
  if (!report.start_tracking || !report.stop_tracking) return null
  const start = Date.parse(report.start_tracking.replace(' ', 'T'))
  const stop = Date.parse(report.stop_tracking.replace(' ', 'T'))
  if (Number.isNaN(start) || Number.isNaN(stop)) return null
  return Math.max(0, Math.round((stop - start) / 1000))
}

export function photoUrl(photo: LeanLensPhoto, cameraId: string): string {
  const img = photo.image ?? ''
  if (/^https?:\/\//.test(img)) return img
  if (img.startsWith('/')) return img
  if (img.startsWith('images/')) return `/${img}`
  return `/images/${cameraId}/${img.replace(/^\/+/, '')}`
}

export function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const date = Date.parse(value.replace(' ', 'T'))
  if (Number.isNaN(date)) return value
  return new Date(date).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`
}

// ---------- queries ----------

interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

async function fetchAllReports(): Promise<{
  reports: LeanLensReport[]
  count: number
}> {
  const MAX_PAGES = 5 // 5 * PAGE_SIZE(20) = 100 latest reports — plenty for the UI
  const first = await api.get<Paginated<LeanLensReport>>('/reports/all_reports/', {
    params: { page: 1 },
  })
  const reports = [...first.data.results]
  let next = first.data.next
  let page = 1
  while (next && page < MAX_PAGES) {
    page += 1
    const { data } = await api.get<Paginated<LeanLensReport>>(
      '/reports/all_reports/',
      { params: { page } }
    )
    reports.push(...data.results)
    next = data.next
  }
  return { reports, count: first.data.count }
}

export function useReports() {
  return useQuery({
    queryKey: ['reports'],
    queryFn: fetchAllReports,
    staleTime: 15_000,
  })
}

export function useCameras() {
  return useQuery({
    queryKey: ['cameras'],
    queryFn: async () => {
      const { data } = await api.get<LeanLensCamera[]>('/camera-algorithms/camera/')
      return data
    },
    staleTime: 30_000,
  })
}

export function useCamerasWithAlgorithms() {
  return useQuery({
    queryKey: ['cameras', 'with-algorithms'],
    queryFn: async () => {
      const [{ data: cameras }, { data: links }] = await Promise.all([
        api.get<LeanLensCamera[]>('/camera-algorithms/camera/'),
        api.get<RawCameraLink[]>('/camera-algorithms/get-process/'),
      ])
      // group the flat camera-algorithm links by camera id
      const byCamera = new Map<string, CameraAlgorithmLink[]>()
      for (const link of links) {
        const id = link.camera?.id
        if (!id) continue
        const arr = byCamera.get(id) ?? []
        arr.push({
          algorithm: link.algorithm,
          process_id: link.process_id,
          is_active: link.is_active,
        })
        byCamera.set(id, arr)
      }
      return cameras.map((c) => ({
        ...c,
        algorithms: byCamera.get(c.id) ?? [],
      })) as CameraWithAlgorithms[]
    },
    staleTime: 30_000,
  })
}

export function useHealthcheck() {
  return useQuery({
    queryKey: ['healthcheck'],
    queryFn: async () => {
      const { data } = await api.get<Healthcheck>('/healthcheck/')
      return data
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
}

// ---------- P2: algorithms (assignment per camera) ----------

export function useAlgorithms() {
  return useQuery({
    queryKey: ['algorithms'],
    queryFn: async () => {
      const { data } = await api.get<AlgorithmDetail[]>(
        '/camera-algorithms/algorithms-detail/'
      )
      return data
    },
    staleTime: 60_000,
  })
}

/**
 * Enable/disable one algorithm for one camera.
 *
 * PFE: the upstream `create-process/` syncs through the algorithms-controller
 * (docker spawns per pid) which is out of service in this deployment; the
 * standalone `leanlens-algo` worker polls `get-process/<ip>/` and suspends
 * detection when the link is gone. `toggle-process/` updates exactly that.
 */
export async function toggleAlgorithm(cameraIp: string, algorithmName: string, enabled: boolean) {
  await api.post('/camera-algorithms/toggle-process/', {
    camera: cameraIp,
    algorithm: algorithmName,
    is_active: enabled,
  })
}

// ---------- P2: company ----------

export function useCompany() {
  return useQuery({
    queryKey: ['company'],
    queryFn: async () => {
      const { data } = await api.get<CompanyInfo[]>('/company/company/')
      // queryset filters my_company + max id -> at most one row
      return data[0] ?? null
    },
    staleTime: 30_000,
  })
}

/** Create when no company row exists yet, PATCH the existing one otherwise. */
export async function saveCompany(company: Omit<CompanyInfo, 'id'> & { id?: number }) {
  const { id, ...fields } = company
  if (id) {
    const { data } = await api.patch<CompanyInfo>(`/company/company/${id}/`, fields)
    return data
  }
  const { data } = await api.post<CompanyInfo>('/company/company/', fields)
  return data
}

// ---------- P2: mailer (emails + working time + smtp) ----------

export function useMailerEmails() {
  return useQuery({
    queryKey: ['mailer', 'emails'],
    queryFn: async () => {
      const { data } = await api.get<MailerEmail[]>('/mailer/emails/')
      return data
    },
    staleTime: 30_000,
  })
}

export async function createMailerEmail(email: string) {
  const { data } = await api.post<MailerEmail>('/mailer/emails/', { email })
  return data
}

export async function updateMailerEmail(id: number, patch: Partial<MailerEmail>) {
  const { data } = await api.patch<MailerEmail>(`/mailer/emails/${id}/`, patch)
  return data
}

export async function deleteMailerEmail(id: number) {
  await api.delete(`/mailer/emails/${id}/`)
}

export function useWorkingTime() {
  return useQuery({
    queryKey: ['mailer', 'working-time'],
    queryFn: async () => {
      const { data } = await api.get<WorkingTime[]>('/mailer/working-time/')
      return data[0] ?? null
    },
    staleTime: 30_000,
  })
}

/** Backend always creates a new WorkingTime row; only the latest is returned. */
export async function saveWorkingTime(timeStart: string, timeEnd: string, days: string[]) {
  const { data } = await api.post<WorkingTime>('/mailer/working-time/', {
    time_start: timeStart,
    time_end: timeEnd,
    days_of_week: days.map((day) => ({ day })),
  })
  return data
}

export function useSmtpSettings() {
  return useQuery({
    queryKey: ['mailer', 'smtp'],
    queryFn: async () => {
      try {
        const { data } = await api.get<SmtpSettings>('/mailer/smtp-settings/')
        return data
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) return null
        throw error
      }
    },
    staleTime: 30_000,
  })
}

/** NOTE: the backend validates the SMTP connection on save (raises on failure). */
export async function saveSmtpSettings(settings: Omit<SmtpSettings, 'id'> & { id?: number }) {
  const { id, ...fields } = settings
  if (id) {
    const { data } = await api.patch<SmtpSettings>(`/mailer/smtp-settings/${id}/`, fields)
    return data
  }
  const { data } = await api.post<SmtpSettings>('/mailer/smtp-settings/', fields)
  return data
}

// ---------- P2: users (djoser) ----------

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<DjoserUser>>('/auth/users/', {
        params: { page: 1 },
      })
      return data.results
    },
    staleTime: 15_000,
  })
}

export async function createUser(username: string, email: string, password: string) {
  const { data } = await api.post<DjoserUser>('/auth/users/', {
    username,
    email,
    password,
  })
  return data
}

/** djoser requires the *requesting* user's password to confirm deletion. */
export async function deleteUser(id: number, currentPassword: string) {
  await api.delete(`/auth/users/${id}/`, { data: { current_password: currentPassword } })
}

/** Change the logged-in user's password (djoser set_password). */
export async function changePassword(currentPassword: string, newPassword: string) {
  await api.post('/auth/users/set_password/', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}

// ---------- P3: cameras CRUD ----------

export interface DiscoveredCamera {
  ip: string
  name?: string
  port?: number
}

export interface NewCamera {
  ip: string
  name?: string
  username?: string
  password?: string
}

/**
 * PFE: the backend creates the Camera row directly (the upstream creation path
 * goes through the onvif/cam-stream services, not deployed here). 409 = exists.
 */
export async function createCamera(camera: NewCamera) {
  const { data } = await api.post<LeanLensCamera>('/camera-algorithms/camera/', {
    ip: camera.ip,
    name: camera.name || undefined,
    username: camera.username || undefined,
    password: camera.password || undefined,
  })
  return data
}

/** Removal also deletes the camera's algorithm links (detection stops). */
export async function deleteCamera(id: string) {
  await api.delete(`/camera-algorithms/delete-camera/${id}/`)
}

/**
 * Subnet scan served by the onviffinder sidecar (host networking) — only
 * available when that service is up; callers must degrade gracefully.
 */
export async function discoverCameras(): Promise<DiscoveredCamera[]> {
  const { data } = await api.get<{ results: unknown }>('/core/find_cameras/')
  const results = Array.isArray(data?.results) ? data.results : []
  return results
    .map((item) => {
      if (typeof item === 'string') return { ip: item }
      if (item && typeof item === 'object') {
        const rec = item as Record<string, unknown>
        const ip = (rec.ip ?? rec.IP ?? rec.address ?? rec.camera_ip) as string | undefined
        if (!ip) return null
        return {
          ip: String(ip),
          name: rec.name ? String(rec.name) : undefined,
          port: typeof rec.port === 'number' ? rec.port : undefined,
        }
      }
      return null
    })
    .filter((c): c is DiscoveredCamera => c !== null)
}

// ---------- P3: GDPR (live anonymisation status) ----------

export interface GdprStatus {
  reported: boolean
  blur_active: boolean
  blur_mode: 'pixelate' | 'blur' | 'solid' | null
  algorithm: string | null
  camera: string | null
  age_seconds: number | null
  stale: boolean
}

/** Heartbeat posted by the leanlens-algo worker (config actually in use). */
export function useGdprStatus() {
  return useQuery({
    queryKey: ['gdpr-status'],
    queryFn: async () => {
      const { data } = await api.get<GdprStatus>('/core/gdpr/status/')
      return data
    },
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}
