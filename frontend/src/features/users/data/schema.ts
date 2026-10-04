/**
 * P2: djoser-backed platform accounts.
 * GET /api/auth/users/ returns {id, username, email} per account.
 */
export interface DjoserAccount {
  id: number
  username: string
  email: string
}
