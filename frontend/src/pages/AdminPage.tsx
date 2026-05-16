import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Clock3,
  Flag,
  KeyRound,
  Plus,
  RefreshCw,
  ServerCog,
  ShieldAlert,
  Users,
} from 'lucide-react'
import toast from 'react-hot-toast'

import { adminApi, type HealthStatus, type SessionRecord } from '@/api/adminApi'
import { userApi } from '@/api/userApi'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { CardBody, CardHeader } from '@/components/ui/Card'
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from '@/components/ui/Cockpit'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { SpinnerOverlay } from '@/components/ui/Spinner'
import { SurfaceTile } from '@/components/ui/SurfaceTile'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '@/components/ui/Table'
import { TabPanel, Tabs } from '@/components/ui/Tabs'
import type { User, UserRoleGrantAuditRecord, UserRoleGrantPolicy, UserRoleGrantSummary } from '@/types/auth'
import { translateText } from '@/lib/i18n'
import { cn, formatDateTime, formatRelativeTime } from '@/lib/utils'

type AdminTab = 'health' | 'users' | 'flags'
type FlagKey =
  | 'monte_carlo'
  | 'digital_twin'
  | 'automl'
  | 'websocket'
  | 'export_parquet'
  | 'billing'
  | 'multi_language'
  | 'dark_mode'
  | 'bos_guidance'
  | 'bos_portability_recommendation'
  | 'bos_audit_export'
  | 'bos_locality_release'
  | 'bos_signal_compile'
  | 'bos_true_boundary_ledger'

interface UserForm {
  username: string
  full_name: string
  email: string
  role: string
  final_action_grants: string[]
  password: string
  is_active: boolean
}

const TABS = [
  { id: 'health', label: 'Runtime', icon: <Activity className="h-4 w-4" /> },
  { id: 'users', label: 'Operators', icon: <Users className="h-4 w-4" /> },
  { id: 'flags', label: 'Feature Gates', icon: <Flag className="h-4 w-4" /> },
]

const BASE_ROLE_OPTIONS = [
  { value: 'operator', label: 'Operator' },
  { value: 'scientist', label: 'Scientist' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'billing', label: 'Billing' },
  { value: 'admin', label: 'Administrator' },
]

const FINAL_ACTION_GRANT_OPTIONS = [
  { value: 'final_release_approver', label: 'Final release approver' },
  { value: 'model_governance_approver', label: 'Model governance approver' },
  { value: 'external_release_share_approver', label: 'External share approver' },
  { value: 'external_release_delivery_approver', label: 'External delivery approver' },
  { value: 'external_runtime_activation_approver', label: 'Runtime activation approver' },
]
const BASE_ROLE_VALUES = new Set(BASE_ROLE_OPTIONS.map((role) => role.value))
const FINAL_ACTION_GRANT_VALUES = new Set(FINAL_ACTION_GRANT_OPTIONS.map((role) => role.value))

const FLAGS: Array<{ key: FlagKey; label: string; description: string }> = [
  { key: 'digital_twin', label: 'Digital twin runtime', description: 'Twin publishing and scenario surfaces.' },
  { key: 'monte_carlo', label: 'Monte Carlo analysis', description: 'Range and confidence analysis in simulation.' },
  {
    key: 'multi_language',
    label: 'Multi-language shell',
    description: 'Translated console strings for multi-site operators.',
  },
  { key: 'billing', label: 'Billing controls', description: 'Billing and plan-governance surfaces.' },
  { key: 'export_parquet', label: 'Parquet export', description: 'Rich export for downstream analysis.' },
  { key: 'websocket', label: 'Realtime transport', description: 'Websocket-fed runtime updates.' },
  { key: 'dark_mode', label: 'Dark mode', description: 'Dark-first operator console rendering.' },
  { key: 'automl', label: 'AutoML surfaces', description: 'Experimental automated model-selection workflows.' },
  { key: 'bos_guidance', label: 'BOS guidance', description: 'Evidence gap guidance and next best actions.' },
  { key: 'bos_portability_recommendation', label: 'BOS recommendation', description: 'Portability recommendation and retuning guidance.' },
  { key: 'bos_audit_export', label: 'BOS audit export', description: 'Audit packet markdown and JSON export.' },
  { key: 'bos_locality_release', label: 'Locality-aware release', description: 'Apply locality shifts during release evaluation.' },
  { key: 'bos_signal_compile', label: 'Signal compile/refresh', description: 'Compile and refresh signal state from batch context.' },
  { key: 'bos_true_boundary_ledger', label: 'True boundary ledger', description: 'Experimental matched-boundary ledger calculations.' },
]

const EMPTY_FORM: UserForm = {
  username: '',
  full_name: '',
  email: '',
  role: 'operator',
  final_action_grants: [],
  password: '',
  is_active: true,
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>('health')
  const [loading, setLoading] = useState(true)
  const [mutating, setMutating] = useState(false)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [roleGrantPolicy, setRoleGrantPolicy] = useState<UserRoleGrantPolicy | null>(null)
  const [roleGrantSummaries, setRoleGrantSummaries] = useState<Record<number, UserRoleGrantSummary>>({})
  const [roleGrantAuditRecords, setRoleGrantAuditRecords] = useState<Record<number, UserRoleGrantAuditRecord[]>>({})
  const [roleGrantAuditLoadingUserId, setRoleGrantAuditLoadingUserId] = useState<number | null>(null)
  const [sessions, setSessions] = useState<SessionRecord[]>([])
  const [flags, setFlags] = useState<Record<string, boolean>>({})
  const [flagSource, setFlagSource] = useState('config')
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<UserForm>(EMPTY_FORM)
  const [editTarget, setEditTarget] = useState<User | null>(null)
  const [editForm, setEditForm] = useState<UserForm>(EMPTY_FORM)
  const [resetTarget, setResetTarget] = useState<User | null>(null)
  const [resetPassword, setResetPassword] = useState('TempReset123!')
  const [statusTarget, setStatusTarget] = useState<User | null>(null)

  const load = async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setLoading(true)
    try {
      const [healthData, userData, sessionData, flagData, policyData] = await Promise.all([
        adminApi.getHealth(),
        adminApi.getUsers(),
        adminApi.getSessions(),
        adminApi.getFeatureFlags().catch(() => ({ flags: {}, source: 'unavailable' })),
        userApi.getRoleGrantPolicy().catch(() => null),
      ])
      const roleGrantEntries = userData
        .map((user) => [user.id, user.role_grant_summary ?? null] as const)
        .filter((entry): entry is readonly [number, UserRoleGrantSummary] => entry[1] !== null)
      setHealth(healthData)
      setUsers(userData)
      setRoleGrantSummaries(Object.fromEntries(roleGrantEntries))
      setSessions(sessionData)
      setFlags(flagData.flags)
      setFlagSource(flagData.source)
      setRoleGrantPolicy(policyData)
      setSelectedUserId((current) =>
        current && userData.some((user) => user.id === current) ? current : (userData[0]?.id ?? null),
      )
    } catch {
      toast.error('Failed to refresh admin control room')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadRoleGrantAuditRecords = async (userId: number) => {
    setRoleGrantAuditLoadingUserId(userId)
    try {
      const history = await userApi.getRoleGrantAuditRecords(userId)
      setRoleGrantAuditRecords((current) => ({
        ...current,
        [userId]: history.audit_records,
      }))
    } catch {
      setRoleGrantAuditRecords((current) => ({
        ...current,
        [userId]: [],
      }))
    } finally {
      setRoleGrantAuditLoadingUserId((current) => (current === userId ? null : current))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (!selectedUserId) return
    void loadRoleGrantAuditRecords(selectedUserId)
  }, [selectedUserId])

  useEffect(() => {
    if (!editTarget) return
    setEditForm({
      username: editTarget.username,
      full_name: editTarget.full_name ?? '',
      email: editTarget.email ?? '',
      role: baseRoleFor(editTarget.role),
      final_action_grants: finalActionGrantsFor(editTarget, roleGrantSummaries),
      password: '',
      is_active: editTarget.is_active,
    })
  }, [editTarget, roleGrantSummaries])

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? users[0] ?? null,
    [selectedUserId, users],
  )

  const summary = useMemo(
    () => ({
      total: users.length,
      active: users.filter((user) => user.is_active).length,
      admins: users.filter((user) => parseRoles(user.role).includes('admin')).length,
      finalActionApprovers: users.filter((user) => finalActionGrantsFor(user, roleGrantSummaries).length > 0).length,
      neverLoggedIn: users.filter((user) => !user.last_login).length,
    }),
    [roleGrantSummaries, users],
  )

  const enabledFlags = useMemo(() => FLAGS.filter((flag) => flags[flag.key]).length, [flags])
  const selectedAuditRecords = selectedUser ? (roleGrantAuditRecords[selectedUser.id] ?? []) : []
  const grantOptions = useMemo(
    () =>
      roleGrantPolicy?.roles?.length
        ? roleGrantPolicy.roles
            .filter((role) => role.grant_endpoint_allowed)
            .map((role) => ({ value: role.role, label: role.label }))
        : FINAL_ACTION_GRANT_OPTIONS,
    [roleGrantPolicy],
  )
  const redisReady = health?.redis === 'connected'
  const runtimeOverrideMode = redisReady ? 'Redis cache online' : 'Database fallback'

  const onCreate = async () => {
    if (!createForm.username || !createForm.full_name || !createForm.email || createForm.password.length < 8) {
      toast.error('Fill in username, name, email, and a password with at least 8 characters')
      return
    }
    setMutating(true)
    try {
      const createdUser = await userApi.create({
        username: createForm.username,
        full_name: createForm.full_name,
        email: createForm.email,
        role: createForm.role,
        password: createForm.password,
      })
      if (createForm.final_action_grants.length > 0) {
        await userApi.replaceRoleGrants(createdUser.id, {
          roles: createForm.final_action_grants,
          reason: 'admin console create',
        })
      }
      toast.success('Operator created')
      setCreateForm(EMPTY_FORM)
      setCreateOpen(false)
      await load({ silent: true })
    } catch (error) {
      toast.error(getError(error, 'Failed to create operator'))
    } finally {
      setMutating(false)
    }
  }

  const onEdit = async () => {
    if (!editTarget) return
    setMutating(true)
    try {
      await userApi.update(editTarget.id, {
        full_name: editForm.full_name,
        email: editForm.email,
        role: editForm.role,
        is_active: editForm.is_active,
      })
      await userApi.replaceRoleGrants(editTarget.id, {
        roles: editForm.final_action_grants,
        reason: 'admin console update',
      })
      toast.success('Operator updated')
      setEditTarget(null)
      await load({ silent: true })
      await loadRoleGrantAuditRecords(editTarget.id)
    } catch (error) {
      toast.error(getError(error, 'Failed to update operator'))
    } finally {
      setMutating(false)
    }
  }

  const onResetPassword = async () => {
    if (!resetTarget) return
    if (resetPassword.trim().length < 8) {
      toast.error('Temporary password must be at least 8 characters')
      return
    }
    setMutating(true)
    try {
      await userApi.resetPassword(resetTarget.id, resetPassword.trim())
      toast.success(`Password reset for ${resetTarget.username}`)
      setResetTarget(null)
      setResetPassword('TempReset123!')
    } catch (error) {
      toast.error(getError(error, 'Failed to reset password'))
    } finally {
      setMutating(false)
    }
  }

  const onToggleStatus = async () => {
    if (!statusTarget) return
    setMutating(true)
    try {
      if (statusTarget.is_active) await userApi.deactivate(statusTarget.id)
      else await userApi.update(statusTarget.id, { is_active: true })
      toast.success(statusTarget.is_active ? 'Operator disabled' : 'Operator enabled')
      setStatusTarget(null)
      await load({ silent: true })
    } catch (error) {
      toast.error(getError(error, 'Failed to update operator status'))
    } finally {
      setMutating(false)
    }
  }

  const onToggleFlag = async (key: FlagKey, enabled: boolean) => {
    setMutating(true)
    try {
      await adminApi.setFeatureFlag(key, enabled)
      setFlags((current) => ({ ...current, [key]: enabled }))
      toast.success(`${labelForFlag(key)} ${enabled ? 'enabled' : 'disabled'}`)
    } catch (error) {
      toast.error(getError(error, 'Failed to update feature flag'))
    } finally {
      setMutating(false)
    }
  }

  const onResetFlag = async (key: FlagKey) => {
    setMutating(true)
    try {
      await adminApi.resetFeatureFlag(key)
      await load({ silent: true })
      toast.success(`${labelForFlag(key)} reset to default`)
    } catch (error) {
      toast.error(getError(error, 'Failed to reset feature flag'))
    } finally {
      setMutating(false)
    }
  }

  if (loading) return <SpinnerOverlay label={translateText("Loading admin control room")} />

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
              <CockpitSectionLabel>Admin</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Control room and operator governance
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Run the local BOS tenancy from one console: runtime health, account lifecycle, session visibility, and feature exposure.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={health?.status === 'healthy' ? 'success' : 'warning'}>
                {health?.status === 'healthy' ? 'Runtime healthy' : 'Runtime degraded'}
              </Badge>
              <Badge variant="info">{`Feature gates: ${enabledFlags}/${FLAGS.length}`}</Badge>
              <Badge variant={redisReady ? 'brand' : 'warning'}>
                {runtimeOverrideMode}
              </Badge>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label="Operators" value={String(summary.total)} hint={`${summary.active} active`} accent="cyan" />
            <CockpitMetric label="Approvers" value={String(summary.finalActionApprovers)} hint={`${summary.admins} base admins`} accent="violet" />
            <CockpitMetric label="Feature gates" value={`${enabledFlags}/${FLAGS.length}`} hint={flagSource} accent="amber" />
            <CockpitMetric label="Uptime" value={formatUptime(health?.uptime_seconds ?? 0)} hint={runtimeOverrideMode} accent="neutral" />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>Admin controls</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Switch between runtime health, operator management, and feature gate overrides from one governance surface.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs tabs={TABS} activeTab={activeTab} onChange={(tab) => setActiveTab(tab as AdminTab)} />
            <Button variant="secondary" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={() => void load()}>
              Refresh
            </Button>
            <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setCreateOpen(true)}>
              New operator
            </Button>
          </div>
        </div>
      </CockpitPanel>

      <TabPanel tabId="health" activeTab={activeTab}>
        <div className="space-y-6">
          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label="Status" value={health?.status ?? 'unknown'} hint="Overall runtime posture" accent="cyan" />
            <CockpitMetric label="Database" value={health?.database ?? 'unknown'} hint="Primary state store" accent="violet" />
            <CockpitMetric label="Redis" value={health?.redis ?? 'unknown'} hint={redisReady ? 'Realtime cache online' : 'Fallback path active'} accent="amber" />
            <CockpitMetric label="Uptime" value={formatUptime(health?.uptime_seconds ?? 0)} hint="Current process lifetime" accent="neutral" />
          </CockpitGrid>
          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
              <CardHeader
                title="Runtime release state"
                description="Fast readout of the backend currently serving this console."
              />
              <CardBody className="space-y-4">
                <SurfaceTile className="assistant-thread-shell">
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-200">
                      <ServerCog className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="assistant-section-kicker !text-surface-500">{translateText("Serving version")}</p>
                      <p className="mt-2 font-mono text-sm text-white">{health?.version ?? translateText('unknown')}</p>
                    </div>
                  </div>
                </SurfaceTile>
                <HealthLine
                  label="Runtime status"
                  value={translateText(health?.status ?? 'unknown')}
                  variant={health?.status === 'healthy' ? 'success' : 'danger'}
                />
                <HealthLine
                  label="Database link"
                  value={translateText(health?.database ?? 'unknown')}
                  variant={health?.database === 'connected' ? 'success' : 'danger'}
                />
                <HealthLine
                  label="Redis link"
                  value={translateText(health?.redis ?? 'unknown')}
                  variant={redisReady ? 'success' : 'warning'}
                />
              </CardBody>
            </CockpitPanel>
            <CockpitPanel className="p-5 lg:p-6">
              <CardHeader title="Attention rail" description="Current local blockers and caveats." />
              <CardBody className="space-y-3">
                {health?.database !== 'connected' ? (
                  <Attention
                    tone="danger"
                    icon={<ShieldAlert className="h-4 w-4" />}
                    text={translateText("Database connectivity is degraded. Operator CRUD and retained state are not trustworthy until this recovers.")}
                  />
                ) : null}
                {!redisReady ? (
                  <Attention
                    tone="warning"
                    icon={<AlertTriangle className="h-4 w-4" />}
                    text={translateText("Redis is offline. Feature-flag changes now persist through the database fallback path, but cache-fed propagation will be slower until Redis recovers.")}
                  />
                ) : null}
                {sessions.length === 0 ? (
                  <Attention
                    tone="warning"
                    icon={<Clock3 className="h-4 w-4" />}
                    text={translateText("No recent sessions were recorded in the last 24 hours.")}
                  />
                ) : null}
                {health?.database === 'connected' && redisReady && sessions.length > 0 ? (
                  <SurfaceTile tone="success" className="px-4 py-3 text-sm text-emerald-100">
                    {translateText("Local runtime dependencies are healthy and operator telemetry is flowing.")}
                  </SurfaceTile>
                ) : null}
              </CardBody>
            </CockpitPanel>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="users" activeTab={activeTab}>
        <div className="space-y-6">
          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label="Total operators" value={String(summary.total)} hint="Provisioned accounts" accent="cyan" />
            <CockpitMetric label="Active" value={String(summary.active)} hint="Enabled access" accent="violet" />
            <CockpitMetric label="Governance grants" value={String(summary.finalActionApprovers)} hint="Elevated approver authority" accent="amber" />
            <CockpitMetric label="Never signed in" value={String(summary.neverLoggedIn)} hint="Awaiting first login" accent="neutral" />
          </CockpitGrid>
          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <CockpitPanel tone="emphasis" className="overflow-hidden p-0">
              <div className="border-b border-white/8 px-6 py-5">
                <CardHeader
                  title="Operator roster"
                  description="Create, edit, suspend, reactivate, and reset credentials without leaving the console."
                />
              </div>
              <div className="px-4 py-4">
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell>Username</TableHeaderCell>
                      <TableHeaderCell>Role</TableHeaderCell>
                      <TableHeaderCell align="center">State</TableHeaderCell>
                      <TableHeaderCell>Last login</TableHeaderCell>
                      <TableHeaderCell>Contact</TableHeaderCell>
                      <TableHeaderCell align="right">Actions</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {users.map((user) => {
                      const grants = finalActionGrantsFor(user, roleGrantSummaries)
                      return (
                        <TableRow
                          key={user.id}
                          onClick={() => setSelectedUserId(user.id)}
                          className={cn(selectedUser?.id === user.id && 'bg-brand-500/10')}
                        >
                          <TableCell>
                            <div>
                              <p className="font-medium text-white">{user.username}</p>
                              <p className="mt-1 text-xs text-surface-500">{user.full_name ?? translateText('Unnamed operator')}</p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-2">
                              <Badge variant={roleVariant(user.role)}>{roleLabel(baseRoleFor(user.role))}</Badge>
                              {grants.length ? (
                                <span className="text-xs text-amber-200">{`${grants.length} governance grant${grants.length > 1 ? 's' : ''}`}</span>
                              ) : null}
                            </div>
                          </TableCell>
                          <TableCell align="center">
                            <Badge variant={user.is_active ? 'success' : 'warning'} dot>
                              {translateText(user.is_active ? 'Enabled' : 'Restricted')}
                            </Badge>
                          </TableCell>
                          <TableCell>{user.last_login ? formatDateTime(user.last_login) : translateText('No sign-in yet')}</TableCell>
                          <TableCell>{user.email ?? translateText('No email')}</TableCell>
                          <TableCell align="right">
                            <div className="flex justify-end gap-2">
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setEditTarget(user)
                                }}
                              >
                                {translateText('Edit')}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setResetTarget(user)
                                }}
                              >
                                {translateText('Reset')}
                              </Button>
                              <Button
                                size="sm"
                                variant={user.is_active ? 'danger' : 'secondary'}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setStatusTarget(user)
                                }}
                              >
                                {translateText(user.is_active ? 'Disable' : 'Enable')}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            </CockpitPanel>
            <div className="space-y-6">
              <CockpitPanel className="p-5 lg:p-6">
                <CardHeader title="Operator detail" description="Pinned detail rail for the selected account." />
                <CardBody className="space-y-4">
                  {selectedUser ? (
                    <>
                      <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="assistant-section-kicker !text-surface-500">Selected account</p>
                            <p className="mt-2 text-lg font-semibold text-white">{selectedUser.full_name}</p>
                            <p className="mt-1 text-sm text-surface-400">@{selectedUser.username}</p>
                          </div>
                          <Badge variant={roleVariant(selectedUser.role)}>{roleLabel(baseRoleFor(selectedUser.role))}</Badge>
                        </div>
                      </div>
                      <Detail label={translateText("State")} value={translateText(selectedUser.is_active ? 'Enabled' : 'Restricted')} />
                      <div className="assistant-meta-panel px-4 py-3">
                        <p className="assistant-section-kicker !text-surface-500">{translateText('Governance grants')}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {finalActionGrantsFor(selectedUser, roleGrantSummaries).length ? (
                            finalActionGrantsFor(selectedUser, roleGrantSummaries).map((grant) => (
                              <Badge key={grant} variant="warning">{roleLabel(grant)}</Badge>
                            ))
                          ) : (
                            <span className="text-sm text-surface-400">{translateText('No explicit governance grants')}</span>
                          )}
                        </div>
                      </div>
                      <div className="assistant-meta-panel px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="assistant-section-kicker !text-surface-500">
                              {translateText('Recent grant history')}
                            </p>
                            <p className="mt-1 text-xs text-surface-500">
                              {translateText('Read-only from user_role_grant_audit_records. Final Action audit stays separate.')}
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                            disabled={roleGrantAuditLoadingUserId === selectedUser.id}
                            onClick={() => void loadRoleGrantAuditRecords(selectedUser.id)}
                          >
                            {translateText('Refresh')}
                          </Button>
                        </div>
                        <div className="mt-4 space-y-3">
                          {roleGrantAuditLoadingUserId === selectedUser.id && selectedAuditRecords.length === 0 ? (
                            <p className="text-sm text-surface-400">{translateText('Loading grant history')}</p>
                          ) : selectedAuditRecords.length ? (
                            selectedAuditRecords.map((record) => (
                              <div key={record.id} className="rounded-xl border border-white/8 bg-black/20 px-3 py-3">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant={auditActionVariant(record.action)}>{auditActionLabel(record.action)}</Badge>
                                  <span className="text-sm font-medium text-white">{roleLabel(record.role)}</span>
                                  <span className="text-xs text-surface-500">
                                    {record.created_at ? formatRelativeTime(record.created_at) : translateText('Unknown time')}
                                  </span>
                                </div>
                                <p className="mt-2 text-xs text-surface-400">
                                  {translateText('Actor')}: {auditActorLabel(record)}
                                </p>
                                <p className="mt-1 text-xs text-surface-400">
                                  {translateText('State')}: {auditStateLabel(record.previous_is_active)} to {auditStateLabel(record.new_is_active)}
                                </p>
                                {record.new_reason || record.previous_reason ? (
                                  <p className="mt-1 text-xs text-surface-400">
                                    {translateText('Reason')}: {record.new_reason ?? record.previous_reason}
                                  </p>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <span className="text-sm text-surface-400">
                              {translateText('No grant history recorded for this account yet.')}
                            </span>
                          )}
                        </div>
                      </div>
                      {roleGrantPolicy ? (
                        <div className="assistant-meta-panel px-4 py-3">
                          <p className="assistant-section-kicker !text-surface-500">{translateText('Grant policy')}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Badge variant="info">{translateText(`Scope: ${roleGrantPolicy.assignment_scope}`)}</Badge>
                            <Badge variant={roleGrantPolicy.legacy_role_fallback ? 'success' : 'warning'}>
                              {translateText('Legacy role fallback')}
                            </Badge>
                            <Badge variant={roleGrantPolicy.admin_grant_allowed ? 'danger' : 'success'}>
                              {translateText(roleGrantPolicy.admin_grant_allowed ? 'Admin grant allowed' : 'Admin grant forbidden')}
                            </Badge>
                            <Badge variant={roleGrantPolicy.self_grant_allowed ? 'danger' : 'success'}>
                              {translateText(roleGrantPolicy.self_grant_allowed ? 'Self grant allowed' : 'Self grant forbidden')}
                            </Badge>
                          </div>
                        </div>
                      ) : null}
                      <Detail label={translateText("Email")} value={selectedUser.email ?? translateText('No email set')} />
                      <Detail
                        label={translateText("Last sign-in")}
                        value={
                          selectedUser.last_login
                            ? formatRelativeTime(selectedUser.last_login)
                            : translateText('Awaiting first sign-in')
                        }
                      />
                      <div className="flex gap-2">
                        <Button
                          variant="secondary"
                          leftIcon={<KeyRound className="h-4 w-4" />}
                          onClick={() => setResetTarget(selectedUser)}
                        >
                          {translateText('Reset password')}
                        </Button>
                        <Button variant="outline" onClick={() => setEditTarget(selectedUser)}>
                          {translateText('Edit access')}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <SurfaceTile className="text-sm text-surface-400">
                      No operator is currently selected.
                    </SurfaceTile>
                  )}
                </CardBody>
              </CockpitPanel>
              <CockpitPanel className="p-5 lg:p-6">
                <CardHeader
                  title="Recent sessions"
                  description="Audit-visible sign-ins recorded in the last 24 hours."
                />
                <CardBody className="space-y-3">
                  {sessions.length ? (
                    sessions.slice(0, 6).map((session, index) => (
                      <div
                        key={`${session.username}-${session.timestamp ?? index}`}
                        className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-white">{session.username}</p>
                            <p className="mt-1 text-xs text-surface-500">{session.user_agent ?? translateText('Unknown client')}</p>
                          </div>
                          <Badge variant="info">
                            {session.timestamp ? formatRelativeTime(session.timestamp) : translateText('Unknown')}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs text-surface-400">{session.ip_address ?? translateText('No IP recorded')}</p>
                      </div>
                    ))
                  ) : (
                    <SurfaceTile className="text-sm text-surface-400">
                      {translateText('No recent sessions were recorded for this tenant.')}
                    </SurfaceTile>
                  )}
                </CardBody>
              </CockpitPanel>
            </div>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="flags" activeTab={activeTab}>
        <div className="space-y-6">
          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-3">
            <CockpitMetric label="Enabled gates" value={String(enabledFlags)} hint="Current overrides live" accent="cyan" />
            <CockpitMetric label="Disabled gates" value={String(FLAGS.length - enabledFlags)} hint="Available but off" accent="violet" />
            <CockpitMetric label="Flag source" value={flagSource} hint={redisReady ? 'Redis-backed propagation' : 'Database fallback'} accent="amber" />
          </CockpitGrid>
          {!redisReady ? (
            <div className="rounded-2xl border border-amber-400/15 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              {translateText('Redis is currently unavailable. Feature-flag overrides are still writable and will persist through the database fallback path, but cache-backed propagation remains degraded until Redis returns.')}
            </div>
          ) : null}
          <div className="grid gap-4 xl:grid-cols-2">
            {FLAGS.map((flag) => {
              const enabled = !!flags[flag.key]
              return (
                <CockpitPanel key={flag.key} tone={enabled ? 'emphasis' : 'default'} className="p-5 lg:p-6">
                  <CardHeader
                    title={flag.label}
                    description={flag.description}
                    action={<Badge variant={enabled ? 'success' : 'neutral'}>{translateText(enabled ? 'Enabled' : 'Disabled')}</Badge>}
                  />
                  <CardBody className="space-y-4">
                    <SurfaceTile className="assistant-thread-shell px-4 py-3">
                      <p className="assistant-section-kicker !text-surface-500">Flag key</p>
                      <p className="mt-2 font-mono text-xs text-surface-300">{flag.key}</p>
                    </SurfaceTile>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant={enabled ? 'secondary' : 'primary'}
                        disabled={mutating}
                        onClick={() => void onToggleFlag(flag.key, !enabled)}
                      >
                        {translateText(enabled ? 'Disable override' : 'Enable override')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={mutating}
                        onClick={() => void onResetFlag(flag.key)}
                      >
                        {translateText('Reset to default')}
                      </Button>
                    </div>
                  </CardBody>
                </CockpitPanel>
              )
            })}
          </div>
        </div>
      </TabPanel>

      <Modal
        open={createOpen}
        onClose={() => !mutating && setCreateOpen(false)}
        title="Create operator"
        description="Provision a new user inside the current local tenant."
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)} disabled={mutating}>
              Cancel
            </Button>
            <Button onClick={() => void onCreate()} loading={mutating}>
              {translateText('Create operator')}
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <Input
            label="Username"
            value={createForm.username}
            onChange={(event) => setCreateForm((current) => ({ ...current, username: event.target.value }))}
          />
          <Input
            label="Full name"
            value={createForm.full_name}
            onChange={(event) => setCreateForm((current) => ({ ...current, full_name: event.target.value }))}
          />
          <Input
            label="Email"
            type="email"
            value={createForm.email}
            onChange={(event) => setCreateForm((current) => ({ ...current, email: event.target.value }))}
          />
          <Select
            label="Base role"
            options={BASE_ROLE_OPTIONS}
            value={createForm.role}
            onChange={(event) => setCreateForm((current) => ({ ...current, role: event.target.value }))}
          />
          <GrantChecklist
            value={createForm.final_action_grants}
            options={grantOptions}
            onChange={(roles) => setCreateForm((current) => ({ ...current, final_action_grants: roles }))}
          />
          <Input
            label="Temporary password"
            type="password"
            value={createForm.password}
            onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={!!editTarget}
        onClose={() => !mutating && setEditTarget(null)}
        title={editTarget ? `Edit ${editTarget.username}` : 'Edit operator'}
        description="Adjust visible profile, role, and activation state for this account."
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditTarget(null)} disabled={mutating}>
              Cancel
            </Button>
            <Button onClick={() => void onEdit()} loading={mutating}>
              {translateText('Save changes')}
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <Input label="Username" value={editForm.username} disabled />
          <Input
            label="Full name"
            value={editForm.full_name}
            onChange={(event) => setEditForm((current) => ({ ...current, full_name: event.target.value }))}
          />
          <Input
            label="Email"
            type="email"
            value={editForm.email}
            onChange={(event) => setEditForm((current) => ({ ...current, email: event.target.value }))}
          />
          <Select
            label="Base role"
            options={BASE_ROLE_OPTIONS}
            value={editForm.role}
            onChange={(event) => setEditForm((current) => ({ ...current, role: event.target.value }))}
          />
          <GrantChecklist
            value={editForm.final_action_grants}
            options={grantOptions}
            onChange={(roles) => setEditForm((current) => ({ ...current, final_action_grants: roles }))}
          />
          <Select
            label="Account state"
            options={[
              { value: 'true', label: 'Enabled' },
              { value: 'false', label: 'Restricted' },
            ]}
            value={String(editForm.is_active)}
            onChange={(event) => setEditForm((current) => ({ ...current, is_active: event.target.value === 'true' }))}
          />
        </div>
      </Modal>

      <Modal
        open={!!resetTarget}
        onClose={() => !mutating && setResetTarget(null)}
        title={resetTarget ? `Reset password for ${resetTarget.username}` : 'Reset password'}
        description="This writes a new password directly for the selected account and clears any active lockout."
        footer={
          <>
            <Button variant="secondary" onClick={() => setResetTarget(null)} disabled={mutating}>
              Cancel
            </Button>
            <Button onClick={() => void onResetPassword()} loading={mutating}>
              {translateText('Reset password')}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="New temporary password"
            type="password"
            value={resetPassword}
            onChange={(event) => setResetPassword(event.target.value)}
          />
          <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
            {translateText('Hand the temporary password to the operator through a secure channel. This reset also clears lockout state.')}
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!statusTarget}
        onClose={() => !mutating && setStatusTarget(null)}
        onConfirm={onToggleStatus}
        loading={mutating}
        title={translateText(statusTarget?.is_active ? 'Disable operator?' : 'Enable operator?')}
        message={
          statusTarget?.is_active
            ? translateText(`This will restrict ${statusTarget.username} from authenticating until the account is re-enabled.`)
            : translateText(`This will reactivate ${statusTarget?.username} for local BOS access.`)
        }
        confirmLabel={translateText(statusTarget?.is_active ? 'Disable' : 'Enable')}
        variant={statusTarget?.is_active ? 'danger' : 'info'}
      />
    </div>
  )
}

function HealthLine({
  label,
  value,
  variant,
}: {
  label: string
  value: string
  variant: 'success' | 'warning' | 'danger'
}) {
  return (
    <SurfaceTile>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="metric-kicker">{label}</p>
          <p className="mt-2 text-sm font-medium text-white">{value}</p>
        </div>
        <Badge variant={variant}>{value}</Badge>
      </div>
    </SurfaceTile>
  )
}

function Attention({ icon, text, tone }: { icon: ReactNode; text: string; tone: 'warning' | 'danger' }) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm',
        tone === 'danger'
          ? 'border-red-400/15 bg-red-500/10 text-red-100'
          : 'border-amber-400/15 bg-amber-500/10 text-amber-100',
      )}
    >
      <span className="mt-0.5 flex-shrink-0">{icon}</span>
      <span>{text}</span>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <SurfaceTile className="assistant-meta-panel px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </SurfaceTile>
  )
}

function GrantChecklist({
  value,
  options,
  onChange,
}: {
  value: string[]
  options: Array<{ value: string; label: string }>
  onChange: (roles: string[]) => void
}) {
  const selected = new Set(value)
  return (
    <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{translateText('Governance grants')}</p>
      <div className="mt-3 grid gap-2">
        {options.map((grant) => (
          <label key={grant.value} className="flex items-center gap-3 text-sm text-surface-200">
            <input
              type="checkbox"
              checked={selected.has(grant.value)}
              onChange={(event) => {
                const next = new Set(selected)
                if (event.target.checked) next.add(grant.value)
                else next.delete(grant.value)
                onChange(options.map((option) => option.value).filter((role) => next.has(role)))
              }}
            />
            <span>{translateText(grant.label)}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

function roleVariant(role: string): 'brand' | 'info' | 'neutral' | 'warning' {
  const roles = parseRoles(role)
  if (roles.includes('admin')) return 'brand'
  if (roles.some((roleName) => roleName.endsWith('_approver'))) return 'warning'
  if (roles.includes('scientist')) return 'info'
  if (roles.includes('billing')) return 'warning'
  return 'neutral'
}

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    admin: 'Administrator',
    scientist: 'Scientist',
    billing: 'Billing',
    operator: 'Operator',
    viewer: 'Viewer',
    final_release_approver: 'Final release approver',
    model_governance_approver: 'Model governance approver',
    external_release_share_approver: 'External share approver',
    external_release_delivery_approver: 'External delivery approver',
    external_runtime_activation_approver: 'Runtime activation approver',
  }
  return parseRoles(role)
    .map((roleName) => labels[roleName] ?? roleName)
    .join(', ')
}

function auditActionLabel(action: UserRoleGrantAuditRecord['action']) {
  const labels: Record<UserRoleGrantAuditRecord['action'], string> = {
    grant: 'Grant',
    revoke: 'Revoke',
    reactivate: 'Reactivate',
    update: 'Update',
  }
  return labels[action] ?? action
}

function auditActionVariant(action: UserRoleGrantAuditRecord['action']): 'success' | 'warning' | 'info' | 'neutral' {
  if (action === 'grant' || action === 'reactivate') return 'success'
  if (action === 'revoke') return 'warning'
  if (action === 'update') return 'info'
  return 'neutral'
}

function auditActorLabel(record: UserRoleGrantAuditRecord) {
  return record.actor_full_name ?? record.actor_username ?? (record.actor_user_id ? `User ${record.actor_user_id}` : 'System')
}

function auditStateLabel(value: boolean | null) {
  if (value === true) return 'active'
  if (value === false) return 'inactive'
  return 'none'
}

function parseRoles(role: string) {
  return role.split(/[\s,;|]+/).filter(Boolean)
}

function baseRoleFor(role: string) {
  return parseRoles(role).find((roleName) => BASE_ROLE_VALUES.has(roleName)) ?? 'viewer'
}

function finalActionGrantsFor(user: User, summaries: Record<number, UserRoleGrantSummary>) {
  const summary = summaries[user.id]
  if (summary) return summary.manageable_governance_grants ?? summary.manageable_final_action_grants
  return parseRoles(user.role)
    .filter((roleName) => FINAL_ACTION_GRANT_VALUES.has(roleName))
    .sort()
}

function labelForFlag(key: string) {
  return FLAGS.find((flag) => flag.key === key)?.label ?? key
}

function formatUptime(seconds: number) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${days}d ${hours}h ${minutes}m`
}

function getError(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
}
