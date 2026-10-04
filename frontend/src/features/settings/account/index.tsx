import { ContentSection } from '../components/content-section'
import { AccountForm } from './account-form'

export function SettingsAccount() {
  return (
    <ContentSection
      title='Account'
      desc='Your platform account (djoser authentication service).'
    >
      <AccountForm />
    </ContentSection>
  )
}
