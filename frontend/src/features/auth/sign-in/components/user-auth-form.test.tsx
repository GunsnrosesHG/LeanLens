import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, type RenderResult } from 'vitest-browser-react'
import { type Locator, userEvent } from 'vitest/browser'
import { UserAuthForm } from './user-auth-form'

const FORM_MESSAGES = {
  usernameEmpty: 'Please enter your username.',
  passwordEmpty: 'Please enter your password.',
} as const

const navigate = vi.fn()
const setUserMock = vi.fn()
const setTokensMock = vi.fn()
const postMock = vi.fn()
const getMock = vi.fn()

// Contrat PFE : login réel contre Django JWT (POST /auth/jwt/create/ puis
// GET /auth/users/me/), session via setTokens/setUser dans l'auth-store.
vi.mock('@/stores/auth-store', () => ({
  useAuthStore: () => ({
    auth: {
      setUser: setUserMock,
      setTokens: setTokensMock,
    },
  }),
}))

vi.mock('@/lib/api', () => ({
  api: {
    post: (...args: unknown[]) => postMock(...args),
    get: (...args: unknown[]) => getMock(...args),
  },
  apiErrorMessage: vi.fn(() => 'Invalid username or password.'),
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

describe('UserAuthForm', () => {
  describe('Rendering without redirectTo', () => {
    let screen: RenderResult
    let usernameInput: Locator
    let passwordInput: Locator
    let signInButton: Locator

    beforeEach(async () => {
      vi.clearAllMocks()
      screen = await render(<UserAuthForm />)
      usernameInput = screen.getByRole('textbox', { name: /^Username$/i })
      passwordInput = screen.getByLabelText(/^Password$/i)
      signInButton = screen.getByRole('button', { name: /^Sign in$/i })
    })

    it('renders username, password, and sign in button', async () => {
      await expect.element(usernameInput).toBeInTheDocument()
      await expect.element(passwordInput).toBeInTheDocument()
      await expect.element(signInButton).toBeInTheDocument()
    })

    it('shows validation messages when submitting empty form', async () => {
      await userEvent.click(signInButton)

      await expect
        .element(screen.getByText(FORM_MESSAGES.usernameEmpty))
        .toBeInTheDocument()
      await expect
        .element(screen.getByText(FORM_MESSAGES.passwordEmpty))
        .toBeInTheDocument()
    })

    it('authenticates and navigates to default route on success', async () => {
      postMock.mockResolvedValue({
        data: { access: 'access-1', refresh: 'refresh-1' },
      })
      getMock.mockResolvedValue({
        data: { id: 1, username: 'admin', email: '' },
      })

      await userEvent.fill(usernameInput, 'admin')
      await userEvent.fill(passwordInput, 'LeanLens2026')
      await userEvent.click(signInButton)

      await vi.waitFor(() => expect(setTokensMock).toHaveBeenCalledOnce())
      expect(setTokensMock).toHaveBeenCalledWith({
        access: 'access-1',
        refresh: 'refresh-1',
      })
      expect(postMock).toHaveBeenCalledWith('/auth/jwt/create/', {
        username: 'admin',
        password: 'LeanLens2026',
      })

      await vi.waitFor(() => expect(setUserMock).toHaveBeenCalledOnce())
      expect(setUserMock).toHaveBeenCalledWith({
        id: 1,
        username: 'admin',
        email: '',
      })

      await vi.waitFor(() =>
        expect(navigate).toHaveBeenCalledWith({ to: '/', replace: true })
      )
    })
  })

  it('navigates to redirectTo when provided', async () => {
    vi.clearAllMocks()
    postMock.mockResolvedValue({
      data: { access: 'access-1', refresh: 'refresh-1' },
    })
    getMock.mockResolvedValue({
      data: { id: 1, username: 'admin', email: '' },
    })

    const { getByRole, getByLabelText } = await render(
      <UserAuthForm redirectTo='/settings' />
    )

    await userEvent.fill(getByRole('textbox', { name: /Username/i }), 'admin')
    await userEvent.fill(getByLabelText('Password'), 'LeanLens2026')

    await userEvent.click(getByRole('button', { name: /Sign in/i }))

    await vi.waitFor(() => expect(setTokensMock).toHaveBeenCalledOnce())
    expect(setUserMock).toHaveBeenCalledOnce()

    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: '/settings',
        replace: true,
      })
    )
  })
})
