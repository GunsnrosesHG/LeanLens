import { ContentSection } from '../components/content-section'
import { CompanyForm } from './company-form'

export function SettingsCompany() {
  return (
    <ContentSection
      title='Company'
      desc='Company profile used across the platform (stored via the company API).'
    >
      <CompanyForm />
    </ContentSection>
  )
}
