import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, Lock, Monitor, Moon, Palette, Save, Sun, User } from 'lucide-react'
import toast from 'react-hot-toast'

import { authApi } from '@/api/authApi'
import { userApi } from '@/api/userApi'
import { useAuthStore } from '@/store/authStore'
import { useTheme } from '@/providers/ThemeProvider'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardFooter, CardHeader } from '@/components/ui/Card'
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from '@/components/ui/Cockpit'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { SurfaceTile, SurfaceTileButton, surfaceTileClasses } from '@/components/ui/SurfaceTile'
import { TabPanel, Tabs } from '@/components/ui/Tabs'
import { getRoleLabel } from '@/types/auth'
import { cn } from '@/lib/utils'

const profileSchema = z.object({
  full_name: z.string().min(1, 'Name is required').max(100),
  email: z.string().email('Invalid email'),
})

type ProfileFormData = z.infer<typeof profileSchema>

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Required'),
    new_password: z.string().min(8, 'Min 8 characters'),
    confirm_password: z.string().min(1, 'Required'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  })

type PasswordFormData = z.infer<typeof passwordSchema>
type ThemeOption = 'light' | 'dark' | 'system'
type PreviewMode = 'light' | 'dark'

const THEME_OPTIONS = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

const THEME_SURFACES: Array<{
  value: ThemeOption
  label: string
  description: string
  icon: typeof Sun
}> = [
  {
    value: 'dark',
    label: 'Dark console',
    description: 'Default operator surface with the strongest hierarchy and reduced glare.',
    icon: Moon,
  },
  {
    value: 'light',
    label: 'Light console',
    description: 'High-clarity alternative for bright workspaces and review sessions.',
    icon: Sun,
  },
  {
    value: 'system',
    label: 'Follow system',
    description: 'Let the console inherit the workstation preference automatically.',
    icon: Monitor,
  },
]

const PREVIEW_MODULES = [
  {
    label: 'SER',
    darkTone: 'bg-emerald-500/18',
    lightTone: 'bg-emerald-100',
  },
  {
    label: 'Queue',
    darkTone: 'bg-sky-500/18',
    lightTone: 'bg-sky-100',
  },
  {
    label: 'Twins',
    darkTone: 'bg-amber-500/18',
    lightTone: 'bg-amber-100',
  },
] as const

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user)
  const setUser = useAuthStore((state) => state.setUser)
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [activeTab, setActiveTab] = useState('profile')

  const tabs = [
    { id: 'profile', label: 'Profile', icon: <User className="h-4 w-4" /> },
    { id: 'password', label: 'Access', icon: <Lock className="h-4 w-4" /> },
    { id: 'preferences', label: 'Console', icon: <Palette className="h-4 w-4" /> },
  ]

  const profileForm = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
    },
  })

  const passwordForm = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  })

  const activeThemeCard = useMemo(
    () => THEME_SURFACES.find((item) => item.value === theme) ?? THEME_SURFACES[0],
    [theme],
  )

  const previewMode: PreviewMode = theme === 'system' ? resolvedTheme : theme
  const accountPosture = user?.is_active ? 'Account active' : 'Account restricted'

  useEffect(() => {
    profileForm.reset({
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
    })
  }, [profileForm, user?.email, user?.full_name])

  const onProfileSubmit = async (data: ProfileFormData) => {
    try {
      const updatedUser = await userApi.updateMe(data)
      setUser(updatedUser)
      profileForm.reset({
        full_name: updatedUser.full_name ?? '',
        email: updatedUser.email ?? '',
      })
      toast.success('Profile updated')
    } catch {
      toast.error('Failed to update profile')
    }
  }

  const onPasswordSubmit = async (data: PasswordFormData) => {
    try {
      await authApi.changePassword({
        current_password: data.current_password,
        new_password: data.new_password,
      })
      const refreshedUser = await authApi.me()
      setUser(refreshedUser)
      toast.success('Password changed')
      passwordForm.reset()
    } catch {
      toast.error('Failed to change password')
    }
  }

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>Settings</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Operator identity and console preferences
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Tune the operator profile, access posture, and presentation defaults that shape this premium control surface.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="info">{getRoleLabel(user?.role ?? 'viewer')}</Badge>
              <Badge variant={user?.is_active ? 'success' : 'warning'}>
                {accountPosture}
              </Badge>
              <Badge variant="brand">{`Theme: ${theme}`}</Badge>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric
              label="Operator"
              value={user?.full_name ?? user?.username ?? 'Unknown'}
              hint={user?.email ?? 'No contact set'}
              accent="cyan"
            />
            <CockpitMetric
              label="Role scope"
              value={getRoleLabel(user?.role ?? 'viewer')}
              hint={accountPosture}
              accent="violet"
            />
            <CockpitMetric
              label="Requested theme"
              value={theme}
              hint={`Resolved ${resolvedTheme}`}
              accent="amber"
            />
            <CockpitMetric
              label="Preview posture"
              value={activeThemeCard.label}
              hint={activeTab === 'preferences' ? 'Console tab open' : `Tab ${activeTab}`}
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>Settings controls</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Switch between profile identity, access rotation, and console presentation without leaving the operator settings cockpit.
            </p>
          </div>
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
        </div>
      </CockpitPanel>

      <TabPanel tabId="profile" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card tone="strong" className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Profile identity"
              description="Update the operator name and contact address shown across the control surface."
            />
            <CardBody>
              <form onSubmit={profileForm.handleSubmit(onProfileSubmit)} className="space-y-4" noValidate>
                <SurfaceTile className="assistant-thread-shell">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="assistant-section-kicker !text-surface-500">Runtime role</p>
                      <p className="mt-2 text-sm font-medium text-white">{user?.username ?? 'Unknown'}</p>
                    </div>
                    <Badge variant="brand">{getRoleLabel(user?.role ?? 'viewer')}</Badge>
                  </div>
                </SurfaceTile>

                <Input
                  label="Full Name"
                  required
                  error={profileForm.formState.errors.full_name?.message}
                  {...profileForm.register('full_name')}
                />
                <Input
                  label="Email"
                  type="email"
                  required
                  error={profileForm.formState.errors.email?.message}
                  {...profileForm.register('email')}
                />
              </form>
            </CardBody>
            <CardFooter>
              <Button
                onClick={profileForm.handleSubmit(onProfileSubmit)}
                loading={profileForm.formState.isSubmitting}
                leftIcon={<Save className="h-4 w-4" />}
              >
                Save profile
              </Button>
            </CardFooter>
          </Card>

          <div className="space-y-6">
            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Identity readout" description="Fast summary of the current operator footprint." />
              <CardBody className="mt-0 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Display name</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{user?.full_name ?? 'Unknown'}</p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Contact</p>
                  <p className="mt-3 text-sm font-medium text-white">{user?.email ?? 'Not set'}</p>
                </SurfaceTile>
              </CardBody>
            </Card>

            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Operator notes" description="How this page is meant to be used." />
              <CardBody className="space-y-3">
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Editable here</p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Human-readable identity and email contact used by surrounding surfaces.
                  </p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Not editable here</p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Role assignment and operator activation remain admin-governed controls.
                  </p>
                </SurfaceTile>
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="password" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <Card tone="strong" className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Credential rotation"
              description="Rotate the operator password without leaving the console."
            />
            <CardBody>
              <form onSubmit={passwordForm.handleSubmit(onPasswordSubmit)} className="space-y-4" noValidate>
                <Input
                  label="Current Password"
                  type="password"
                  autoComplete="current-password"
                  required
                  error={passwordForm.formState.errors.current_password?.message}
                  {...passwordForm.register('current_password')}
                />
                <Input
                  label="New Password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={passwordForm.formState.errors.new_password?.message}
                  {...passwordForm.register('new_password')}
                />
                <Input
                  label="Confirm New Password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={passwordForm.formState.errors.confirm_password?.message}
                  {...passwordForm.register('confirm_password')}
                />
              </form>
            </CardBody>
            <CardFooter>
              <Button
                onClick={passwordForm.handleSubmit(onPasswordSubmit)}
                loading={passwordForm.formState.isSubmitting}
                leftIcon={<Lock className="h-4 w-4" />}
              >
                Update password
              </Button>
            </CardFooter>
          </Card>

          <div className="space-y-6">
            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Access posture" description="Current state of the operator account." />
              <CardBody className="mt-0 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Access state</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{user?.is_active ? 'Enabled' : 'Restricted'}</p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Role scope</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{getRoleLabel(user?.role ?? 'viewer')}</p>
                </SurfaceTile>
              </CardBody>
            </Card>

            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Rotation guidance" description="Expected operator hygiene for this console." />
              <CardBody className="space-y-3">
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Minimum bar</p>
                  <p className="mt-2 text-sm text-surface-300">
                    Use at least 8 characters and avoid reusing operator credentials from adjacent systems.
                  </p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">When to rotate</p>
                  <p className="mt-2 text-sm text-surface-300">
                    Rotate after shared-workstation use, access handoff, or any suspected credential exposure.
                  </p>
                </SurfaceTile>
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="preferences" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card tone="strong" className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Console presentation"
              description="Choose how the premium operator console should render across sessions."
            />
            <CardBody className="space-y-5">
              <Select
                label="Theme"
                options={THEME_OPTIONS}
                value={theme}
                onChange={(event) => setTheme(event.target.value as ThemeOption)}
              />

              <div className="grid gap-3">
                {THEME_SURFACES.map((item) => {
                  const Icon = item.icon
                  const active = item.value === theme

                  return (
                    <SurfaceTileButton
                      key={item.value}
                      onClick={() => setTheme(item.value)}
                      selected={active}
                      className="flex items-start gap-4"
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-200">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="min-w-0">
                        <span className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{item.label}</span>
                          {active ? <Badge variant="brand">Selected</Badge> : null}
                        </span>
                        <span className="mt-2 block text-sm leading-6 text-surface-400">{item.description}</span>
                      </span>
                    </SurfaceTileButton>
                  )
                })}
              </div>

              <ThemeConsolePreview mode={previewMode} />
            </CardBody>
          </Card>

          <div className="space-y-6">
            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Display resolution" description="Resolved theme state after applying system logic." />
              <CardBody className="mt-0 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Requested mode</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{theme}</p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell rounded-[22px]">
                  <p className="assistant-section-kicker">Resolved mode</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{resolvedTheme}</p>
                </SurfaceTile>
              </CardBody>
            </Card>

            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader
                title="Operator reading mode"
                description="How the current theme affects the control surface."
              />
              <CardBody className="space-y-3">
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Active theme</p>
                  <p className="mt-2 text-sm font-medium text-white">{activeThemeCard.label}</p>
                  <p className="mt-2 text-sm leading-6 text-surface-400">{activeThemeCard.description}</p>
                </SurfaceTile>
                <SurfaceTile className="assistant-thread-shell px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-sky-200" />
                    <p className="text-sm font-medium text-white">Usage note</p>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-surface-400">
                    Dark mode preserves the highest visual contrast in dense analytic views, while light mode can help
                    during document review or bright-room sessions.
                  </p>
                </SurfaceTile>
                {theme === 'system' ? (
                  <SurfaceTile tone="info" className="px-4 py-3 text-sm text-sky-100">
                    System mode is currently resolving to <span className="font-semibold">{resolvedTheme}</span>.
                  </SurfaceTile>
                ) : null}
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>
    </div>
  )
}

function ThemeConsolePreview({ mode }: { mode: PreviewMode }) {
  const isDark = mode === 'dark'
  const previewReadouts = isDark
    ? [
        { label: 'Contrast', value: '92%', tone: 'success' as const },
        { label: 'Focus drift', value: 'Low', tone: 'info' as const },
        { label: 'Queue noise', value: '18m', tone: 'neutral' as const },
      ]
    : [
        { label: 'Contrast', value: '78%', tone: 'info' as const },
        { label: 'Review mode', value: 'Paper', tone: 'success' as const },
        { label: 'Glare load', value: 'Moderate', tone: 'warning' as const },
      ]

  return (
    <SurfaceTile className="rounded-[28px] border-white/10 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="metric-kicker">Theme preview</p>
          <p className="mt-2 text-sm font-medium text-white">
            {isDark ? 'Dark console rendering' : 'Light console rendering'}
          </p>
        </div>
        <Badge variant={isDark ? 'success' : 'info'}>{mode}</Badge>
      </div>

      <div className="mt-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          {previewReadouts.map((readout, index) => (
            <motion.div
              key={`${mode}-${readout.label}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05, duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className={cn(
                surfaceTileClasses(),
                'py-3',
                isDark ? 'border-white/8 bg-white/5' : 'border-slate-300/70 bg-white/90',
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <p className={cn('metric-kicker', isDark ? 'text-surface-400' : 'text-slate-500')}>{readout.label}</p>
                <Badge variant={readout.tone} size="xs">
                  Live
                </Badge>
              </div>
              <p className={cn('mt-2 text-base font-semibold', isDark ? 'text-white' : 'text-slate-900')}>
                {readout.value}
              </p>
            </motion.div>
          ))}
        </div>

        <div
          className={cn(
            'relative overflow-hidden rounded-[24px] border p-4 transition-all duration-200',
            isDark ? 'border-white/10 bg-[#08111d]' : 'border-slate-300/80 bg-[#f7fafc]',
          )}
        >
          <motion.div
            className={cn(
              'pointer-events-none absolute inset-y-0 left-[-20%] w-[42%] blur-3xl',
              isDark ? 'bg-emerald-500/18' : 'bg-sky-300/35',
            )}
            animate={{ x: ['-10%', '110%', '-10%'], opacity: [0.16, 0.3, 0.16] }}
            transition={{ duration: 6.2, repeat: Infinity, ease: 'easeInOut' }}
          />

          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0, y: 10, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.985 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="relative z-[1] grid gap-4 lg:grid-cols-[0.34fr_0.66fr]"
            >
              <SurfaceTile
                className={cn(
                  'rounded-[20px] p-4',
                  isDark ? 'border-white/8 bg-white/5' : 'border-slate-300/70 bg-white/95',
                )}
              >
                <div className="flex items-center gap-2">
                  <motion.span
                    className={cn(
                      'flex h-9 w-9 items-center justify-center rounded-2xl',
                      isDark ? 'bg-emerald-500/20' : 'bg-emerald-100',
                    )}
                    animate={{ scale: [1, 1.08, 1] }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                  >
                    <motion.span
                      className={cn('h-2.5 w-2.5 rounded-full', isDark ? 'bg-emerald-200' : 'bg-emerald-500')}
                      animate={{ opacity: [0.6, 1, 0.6] }}
                      transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  </motion.span>
                  <div>
                    <div className={cn('h-2.5 w-24 rounded-full', isDark ? 'bg-white/80' : 'bg-slate-800')} />
                    <div className={cn('mt-2 h-2 w-20 rounded-full', isDark ? 'bg-white/20' : 'bg-slate-300')} />
                  </div>
                </div>

                <div className="mt-5 space-y-2">
                  {[0, 1, 2].map((item) => (
                    <motion.div
                      key={`${mode}-rail-${item}`}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: item * 0.05, duration: 0.2 }}
                      className={cn(
                        surfaceTileClasses(item === 0 && isDark ? 'success' : 'default'),
                        'px-3 py-3',
                        item === 0
                          ? isDark
                            ? 'border-emerald-400/20 bg-emerald-500/12'
                            : 'border-emerald-200 bg-emerald-50'
                          : isDark
                            ? 'border-white/8 bg-white/4'
                            : 'border-slate-200 bg-slate-50',
                      )}
                    >
                      <motion.div
                        className={cn('h-2.5 rounded-full', isDark ? 'bg-white/80' : 'bg-slate-800')}
                        animate={{ width: item === 0 ? [72, 84, 72] : [64, 76, 64] }}
                        transition={{ duration: 2.4 + item * 0.2, repeat: Infinity, ease: 'easeInOut' }}
                      />
                      <motion.div
                        className={cn('mt-2 h-2 rounded-full', isDark ? 'bg-white/15' : 'bg-slate-300')}
                        animate={{ width: [92, 106, 92] }}
                        transition={{ duration: 2.8 + item * 0.25, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    </motion.div>
                  ))}
                </div>
              </SurfaceTile>

              <div className="space-y-4">
                <SurfaceTile
                  className={cn(
                    'rounded-[20px] px-4 py-3',
                    isDark ? 'border-white/8 bg-white/5' : 'border-slate-300/70 bg-white/95',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className={cn('h-2.5 w-28 rounded-full', isDark ? 'bg-white/85' : 'bg-slate-800')} />
                      <div className={cn('mt-2 h-2 w-40 rounded-full', isDark ? 'bg-white/15' : 'bg-slate-300')} />
                    </div>
                    <div className="flex gap-2">
                      <motion.span
                        className={cn('h-8 rounded-2xl', isDark ? 'bg-white/8' : 'bg-slate-100')}
                        animate={{ width: [56, 70, 56] }}
                        transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
                      />
                      <motion.span
                        className={cn('h-8 rounded-2xl', isDark ? 'bg-emerald-500/20' : 'bg-emerald-100')}
                        animate={{ width: [36, 48, 36] }}
                        transition={{ duration: 1.9, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    </div>
                  </div>
                </SurfaceTile>

                <div className="grid gap-3 sm:grid-cols-3">
                  {PREVIEW_MODULES.map((item, index) => (
                    <motion.div
                      key={`${mode}-${item.label}`}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 + index * 0.05, duration: 0.2 }}
                      className={cn(
                        surfaceTileClasses(),
                        'rounded-[20px]',
                        isDark ? 'border-white/8 bg-white/5' : 'border-slate-300/70 bg-white/95',
                      )}
                    >
                      <div
                        className={cn(
                          'text-[10px] uppercase tracking-[0.24em]',
                          isDark ? 'text-slate-400' : 'text-slate-500',
                        )}
                      >
                        {item.label}
                      </div>
                      <motion.div
                        className={cn('mt-3 h-7 origin-left rounded-full', isDark ? item.darkTone : item.lightTone)}
                        animate={{ scaleX: [0.68, 1, 0.82] }}
                        transition={{ duration: 2 + index * 0.25, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    </motion.div>
                  ))}
                </div>

                <SurfaceTile
                  className={cn(
                    'rounded-[20px] p-4',
                    isDark ? 'border-white/8 bg-white/5' : 'border-slate-300/70 bg-white/95',
                  )}
                >
                  <div className={cn('h-2.5 w-32 rounded-full', isDark ? 'bg-white/85' : 'bg-slate-800')} />
                  <div className="mt-4 grid gap-3 sm:grid-cols-[0.58fr_0.42fr]">
                    <div
                      className={cn('relative overflow-hidden rounded-2xl', isDark ? 'bg-white/6' : 'bg-slate-100')}
                      style={{ height: 108 }}
                    >
                      <motion.div
                        className={cn(
                          'absolute bottom-0 left-[10%] w-[14%] rounded-t-2xl',
                          isDark ? 'bg-emerald-500/24' : 'bg-emerald-200',
                        )}
                        animate={{ height: [30, 64, 38] }}
                        transition={{ duration: 2.3, repeat: Infinity, ease: 'easeInOut' }}
                      />
                      <motion.div
                        className={cn(
                          'absolute bottom-0 left-[34%] w-[14%] rounded-t-2xl',
                          isDark ? 'bg-sky-500/24' : 'bg-sky-200',
                        )}
                        animate={{ height: [54, 82, 60] }}
                        transition={{ duration: 2.1, repeat: Infinity, ease: 'easeInOut' }}
                      />
                      <motion.div
                        className={cn(
                          'absolute bottom-0 left-[58%] w-[14%] rounded-t-2xl',
                          isDark ? 'bg-amber-500/24' : 'bg-amber-200',
                        )}
                        animate={{ height: [42, 74, 50] }}
                        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    </div>
                    <div className="space-y-3">
                      {[0, 1].map((item) => (
                        <SurfaceTile
                          key={`${mode}-signal-${item}`}
                          className={cn('p-3', isDark ? 'border-white/8 bg-white/6' : 'border-slate-200 bg-slate-100')}
                        >
                          <div className={cn('h-2.5 w-20 rounded-full', isDark ? 'bg-white/80' : 'bg-slate-800')} />
                          <motion.div
                            className={cn('mt-3 h-2 rounded-full', isDark ? 'bg-white/15' : 'bg-slate-300')}
                            animate={{ width: item === 0 ? [64, 92, 64] : [84, 56, 84] }}
                            transition={{ duration: 2.2 + item * 0.3, repeat: Infinity, ease: 'easeInOut' }}
                          />
                        </SurfaceTile>
                      ))}
                    </div>
                  </div>
                </SurfaceTile>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </SurfaceTile>
  )
}
