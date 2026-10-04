import {
  Frame,
  LayoutDashboard,
  Monitor,
  Bell,
  Palette,
  Settings,
  Camera,
  FileSearch,
  User,
  Users as UsersIcon,
  Building2,
  Workflow,
  ShieldCheck,
} from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  user: {
    name: 'admin',
    email: '',
    avatar: '',
  },
  teams: [
    {
      name: 'LeanLens',
      logo: Frame,
      plan: 'Smart Monitoring',
    },
  ],
  navGroups: [
    {
      title: 'Monitoring',
      items: [
        {
          title: 'Dashboard',
          url: '/',
          icon: LayoutDashboard,
        },
        {
          title: 'Cameras',
          url: '/cameras',
          icon: Camera,
        },
        {
          title: 'Algorithms',
          url: '/algorithms',
          icon: Workflow,
        },
        {
          title: 'Reports',
          url: '/reports',
          icon: FileSearch,
          badge: 'live',
        },
        {
          title: 'GDPR',
          url: '/gdpr',
          icon: ShieldCheck,
        },
      ],
    },
    {
      title: 'Settings',
      items: [
        {
          title: 'Account',
          url: '/settings/account',
          icon: User,
        },
        {
          title: 'Company',
          url: '/settings/company',
          icon: Building2,
        },
        {
          title: 'Users',
          url: '/users',
          icon: UsersIcon,
        },
        {
          title: 'Appearance',
          url: '/settings/appearance',
          icon: Palette,
        },
        {
          title: 'Notifications',
          url: '/settings/notifications',
          icon: Bell,
        },
        {
          title: 'Display',
          url: '/settings/display',
          icon: Monitor,
        },
      ],
    },
    {
      title: 'Platform',
      items: [
        {
          title: 'Settings',
          url: '/settings',
          icon: Settings,
        },
      ],
    },
  ],
}
