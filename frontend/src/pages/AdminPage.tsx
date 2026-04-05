import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Flag,
  Pin,
  RefreshCw,
  ServerCog,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableSkeleton,
} from "@/components/ui/Table";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { cn, formatDateTime, formatRelativeTime } from "@/lib/utils";

interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  version: string;
  uptime_seconds: number;
}

interface UserRecord {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
}

type Severity = "healthy" | "watch" | "critical";

const TABS = [
  { id: "health", label: "Runtime", icon: <Activity className="h-4 w-4" /> },
  { id: "users", label: "Operators", icon: <Users className="h-4 w-4" /> },
  { id: "flags", label: "Feature Gates", icon: <Flag className="h-4 w-4" /> },
];

const FEATURE_FLAGS = [
  {
    key: "VITE_ENABLE_DIGITAL_TWINS",
    label: "Digital Twins",
    description: "Expose digital twin creation and runtime simulation flows.",
  },
  {
    key: "VITE_ENABLE_SUSTAINABILITY",
    label: "Sustainability Surface",
    description: "Expose TEA, energy, and environmental accounting surfaces.",
  },
  {
    key: "VITE_ENABLE_FORECAST",
    label: "Forecast Surface",
    description: "Expose signal drift and time-series forecast tooling.",
  },
];

const SEVERITY_STYLES: Record<Severity, { badge: "success" | "warning" | "danger"; tone: string }> = {
  healthy: {
    badge: "success",
    tone: "border-emerald-400/15 bg-emerald-500/10 text-emerald-100",
  },
  watch: {
    badge: "warning",
    tone: "border-amber-400/15 bg-amber-500/10 text-amber-100",
  },
  critical: {
    badge: "danger",
    tone: "border-red-400/15 bg-red-500/10 text-red-100",
  },
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState("health");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [hoveredUserId, setHoveredUserId] = useState<number | null>(null);

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const { default: client } = await import("@/api/client");
      const { data } = await client.get("/health");
      setHealth(data);
    } catch {
      toast.error("Failed to fetch health status");
    } finally {
      setHealthLoading(false);
    }
  };

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const { default: client } = await import("@/api/client");
      const { data } = await client.get("/admin/users");
      setUsers(data.items ?? data);
    } catch {
      toast.error("Failed to fetch users");
    } finally {
      setUsersLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    fetchUsers();
  }, []);

  useEffect(() => {
    if (!users.length) {
      setSelectedUserId(null);
      return;
    }

    setSelectedUserId((current) =>
      current && users.some((user) => user.id === current) ? current : users[0].id,
    );
  }, [users]);

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const userSummary = useMemo(() => {
    const active = users.filter((user) => user.is_active).length;
    const admins = users.filter((user) => user.role === "admin").length;
    const noRecentLogin = users.filter((user) => !user.last_login).length;
    const inactiveAdmins = users.filter((user) => user.role === "admin" && !user.is_active).length;

    return {
      total: users.length,
      active,
      admins,
      noRecentLogin,
      inactiveAdmins,
    };
  }, [users]);

  const enabledFlags = useMemo(
    () =>
      FEATURE_FLAGS.filter(
        (flag) => import.meta.env[flag.key as keyof ImportMetaEnv] === "true",
      ).length,
    [],
  );

  const runtimeSignals = useMemo(() => {
    if (!health) return [];

    return [
      {
        label: "Runtime status",
        value: health.status,
        severity: health.status === "healthy" ? "healthy" : "critical",
        hint: "Top-level service heartbeat for the control plane.",
      },
      {
        label: "Database link",
        value: health.database,
        severity: health.database === "connected" ? "healthy" : "critical",
        hint: "Primary persistence path for operator and batch surfaces.",
      },
      {
        label: "Redis link",
        value: health.redis,
        severity: health.redis === "connected" ? "healthy" : "watch",
        hint: "Queue, cache, and short-lived orchestration support.",
      },
    ] as Array<{
      label: string;
      value: string;
      severity: Severity;
      hint: string;
    }>;
  }, [health]);

  const governanceSignals = useMemo(
    () =>
      [
        {
          label: "Admin coverage",
          value: `${userSummary.admins}`,
          severity: userSummary.admins === 0 ? "critical" : "healthy",
          hint: "At least one administrator should remain active.",
        },
        {
          label: "Never signed in",
          value: `${userSummary.noRecentLogin}`,
          severity: userSummary.noRecentLogin > 0 ? "watch" : "healthy",
          hint: "Operators without login history may still need provisioning review.",
        },
        {
          label: "Inactive admins",
          value: `${userSummary.inactiveAdmins}`,
          severity: userSummary.inactiveAdmins > 0 ? "watch" : "healthy",
          hint: "Privileged accounts marked inactive should be confirmed intentionally disabled.",
        },
      ] as Array<{
        label: string;
        value: string;
        severity: Severity;
        hint: string;
      }>,
    [userSummary],
  );

  const runtimeAttention = useMemo(() => {
    const items: Array<{ text: string; severity: Severity }> = [];

    if (!health) return items;
    if (health.status !== "healthy") {
      items.push({ text: "Runtime health is not reporting a healthy state.", severity: "critical" });
    }
    if (health.database !== "connected") {
      items.push({ text: "Database connectivity requires immediate attention.", severity: "critical" });
    }
    if (health.redis !== "connected") {
      items.push({ text: "Redis is not connected, which can affect queue or cache behavior.", severity: "watch" });
    }
    if (userSummary.noRecentLogin > 0) {
      items.push({ text: "Some operator accounts have never signed in and may need validation.", severity: "watch" });
    }

    return items;
  }, [health, userSummary.noRecentLogin]);

  const gradeUser = (user: UserRecord): { label: string; severity: Severity } => {
    if (!user.is_active) return { label: "Restricted", severity: "critical" };
    if (user.role === "admin" && !user.last_login) return { label: "Review", severity: "watch" };
    if (!user.last_login) return { label: "Pending first sign-in", severity: "watch" };
    return { label: "In spec", severity: "healthy" };
  };

  const activeRosterUser = useMemo(() => {
    const targetId = hoveredUserId ?? selectedUserId;
    return users.find((user) => user.id === targetId) ?? users[0] ?? null;
  }, [hoveredUserId, selectedUserId, users]);

  const activeRosterReview = activeRosterUser ? gradeUser(activeRosterUser) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Control room and operator governance"
        description="Review runtime health, operator access, and the frontend feature-gate posture that defines which premium surfaces are live."
        badges={[
          {
            label: health?.status === "healthy" ? "Runtime healthy" : "Runtime review pending",
            variant: health?.status === "healthy" ? "success" : "warning",
          },
          { label: `Feature gates: ${enabledFlags}/${FEATURE_FLAGS.length}`, variant: "info" },
          { label: "Admin surface", variant: "brand" },
        ]}
        stats={[
          {
            label: "Runtime",
            value: health?.status ?? "Loading",
            hint: "Current control-plane posture",
          },
          {
            label: "Database",
            value: health?.database ?? "Loading",
            hint: "Primary persistence link",
          },
          {
            label: "Operators",
            value: userSummary.total || (usersLoading ? "Loading" : 0),
            hint: "Accounts under governance",
          },
          {
            label: "Release version",
            value: health?.version ?? "Loading",
            hint: "Deployed runtime version",
          },
        ]}
      />

      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <TabPanel tabId="health" activeTab={activeTab}>
        {healthLoading ? (
          <SpinnerOverlay label="Checking control-room health" />
        ) : health ? (
          <div className="space-y-6">
            <div className="flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<RefreshCw className="h-4 w-4" />}
                onClick={fetchHealth}
              >
                Refresh runtime
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Status"
                value={
                  <Badge variant={health.status === "healthy" ? "success" : "danger"} dot>
                    {health.status}
                  </Badge>
                }
                color="green"
              />
              <StatCard
                label="Database"
                value={
                  <Badge variant={health.database === "connected" ? "success" : "danger"} dot>
                    {health.database}
                  </Badge>
                }
                color="blue"
              />
              <StatCard
                label="Redis"
                value={
                  <Badge variant={health.redis === "connected" ? "success" : "warning"} dot>
                    {health.redis}
                  </Badge>
                }
                color="amber"
              />
              <StatCard label="Uptime" value={formatUptime(health.uptime_seconds)} color="neutral" />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
              <Card tone="strong">
                <CardHeader
                  title="Runtime release state"
                  description="Quick readout of the deployed version currently serving this console."
                />
                <CardBody className="space-y-4">
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
                    <div className="flex items-center gap-3">
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-200">
                        <ServerCog className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="metric-kicker">Serving version</p>
                        <p className="mt-2 font-mono text-sm text-white">{health.version}</p>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3">
                    {runtimeSignals.map((signal) => (
                      <div
                        key={signal.label}
                        className={cn(
                          "rounded-2xl border px-4 py-3",
                          SEVERITY_STYLES[signal.severity].tone,
                        )}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="metric-kicker text-current/70">{signal.label}</p>
                            <p className="mt-2 text-sm font-medium">{signal.value}</p>
                          </div>
                          <Badge variant={SEVERITY_STYLES[signal.severity].badge}>{signal.severity}</Badge>
                        </div>
                        <p className="mt-2 text-xs text-current/70">{signal.hint}</p>
                      </div>
                    ))}
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="Attention rail"
                  description="Conditions that deserve immediate operator review."
                />
                <CardBody className="space-y-3">
                  {runtimeAttention.length ? (
                    runtimeAttention.map((item) => (
                      <div
                        key={item.text}
                        className={cn(
                          "flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm",
                          SEVERITY_STYLES[item.severity].tone,
                        )}
                      >
                        {item.severity === "critical" ? (
                          <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
                        ) : (
                          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                        )}
                        <span>{item.text}</span>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                      No immediate runtime concerns are visible from the current health snapshot.
                    </div>
                  )}
                </CardBody>
              </Card>
            </div>
          </div>
        ) : null}
      </TabPanel>

      <TabPanel tabId="users" activeTab={activeTab}>
        {usersLoading ? (
          <TableSkeleton rows={5} cols={7} />
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Total operators" value={userSummary.total} color="blue" />
              <StatCard label="Active" value={userSummary.active} color="green" />
              <StatCard label="Admins" value={userSummary.admins} color="amber" />
              <StatCard label="No sign-in yet" value={userSummary.noRecentLogin} color="neutral" />
            </div>

            <Card>
              <CardHeader
                title="Governance grading"
                description="Quick classification of operator-account conditions."
              />
              <CardBody className="grid gap-3 sm:grid-cols-3">
                {governanceSignals.map((signal) => (
                  <div
                    key={signal.label}
                    className={cn(
                      "rounded-2xl border px-4 py-4",
                      SEVERITY_STYLES[signal.severity].tone,
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="metric-kicker text-current/70">{signal.label}</p>
                      <Badge variant={SEVERITY_STYLES[signal.severity].badge}>{signal.severity}</Badge>
                    </div>
                    <p className="mt-3 text-2xl font-semibold">{signal.value}</p>
                    <p className="mt-2 text-xs text-current/70">{signal.hint}</p>
                  </div>
                ))}
              </CardBody>
            </Card>

            <Card tone="strong" noPadding>
              <div className="border-b border-white/8 px-6 py-5">
                <CardHeader
                  title="Operator roster"
                  description="Role, activation state, and latest sign-in across governed accounts."
                />
              </div>
              {activeRosterUser && activeRosterReview ? (
                <div className="grid gap-4 border-b border-white/8 px-6 py-5 lg:grid-cols-[1.15fr_0.85fr]">
                  <div className="rounded-[24px] border border-white/8 bg-white/5 px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="metric-kicker">Active row preview</p>
                        <p className="mt-2 text-lg font-semibold text-white">
                          {activeRosterUser.full_name}
                        </p>
                        <p className="mt-1 text-sm text-surface-400">
                          @{activeRosterUser.username} · {activeRosterUser.email}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant={getRoleVariant(activeRosterUser.role)}
                          size="sm"
                        >
                          {activeRosterUser.role}
                        </Badge>
                        <Badge
                          variant={SEVERITY_STYLES[activeRosterReview.severity].badge}
                          size="sm"
                        >
                          {activeRosterReview.label}
                        </Badge>
                        {selectedUserId === activeRosterUser.id ? (
                          <Badge variant="brand" size="sm">
                            Pinned
                          </Badge>
                        ) : hoveredUserId === activeRosterUser.id ? (
                          <Badge variant="info" size="sm">
                            Hover preview
                          </Badge>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                        <p className="metric-kicker">Account state</p>
                        <p className="mt-2 text-sm font-medium text-white">
                          {activeRosterUser.is_active ? "Enabled" : "Restricted"}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                        <p className="metric-kicker">Last sign-in</p>
                        <p className="mt-2 text-sm font-medium text-white">
                          {activeRosterUser.last_login
                            ? formatRelativeTime(activeRosterUser.last_login)
                            : "Awaiting first sign-in"}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                        <p className="metric-kicker">Next review cue</p>
                        <p className="mt-2 text-sm font-medium text-white">
                          {getReviewCue(activeRosterUser, activeRosterReview.severity)}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div
                    className={cn(
                      "rounded-[24px] border px-4 py-4",
                      SEVERITY_STYLES[activeRosterReview.severity].tone,
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="metric-kicker text-current/70">Detail affordance</p>
                        <p className="mt-2 text-sm font-medium">
                          Hover a row to preview, click to pin the detail rail.
                        </p>
                      </div>
                      <Pin className="h-4 w-4" />
                    </div>
                    <p className="mt-4 text-sm text-current/80">
                      {activeRosterUser.last_login
                        ? `Last recorded sign-in: ${formatDateTime(activeRosterUser.last_login)}`
                        : "This operator has not completed an initial sign-in yet."}
                    </p>
                  </div>
                </div>
              ) : null}
              <div className="px-4 pb-4 pt-4">
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell>Username</TableHeaderCell>
                      <TableHeaderCell>Full Name</TableHeaderCell>
                      <TableHeaderCell>Email</TableHeaderCell>
                      <TableHeaderCell align="center">Role</TableHeaderCell>
                      <TableHeaderCell align="center">Active</TableHeaderCell>
                      <TableHeaderCell align="center">Review</TableHeaderCell>
                      <TableHeaderCell>Last Login</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {users.map((user) => {
                      const review = gradeUser(user);
                      const isActiveRow = activeRosterUser?.id === user.id;
                      const isPinned = selectedUserId === user.id;

                      return (
                        <TableRow
                          key={user.id}
                          onClick={() => setSelectedUserId(user.id)}
                          onMouseEnter={() => setHoveredUserId(user.id)}
                          onMouseLeave={() => setHoveredUserId(null)}
                          className={cn(
                            "transition-colors duration-150",
                            isActiveRow
                              ? "bg-brand-500/10"
                              : "hover:bg-white/8",
                          )}
                        >
                          <TableCell className="min-w-[11rem]">
                            <div className="flex items-center justify-between gap-3">
                              <span
                                className={cn(
                                  "font-medium text-surface-900 dark:text-surface-100",
                                  isActiveRow && "text-white",
                                )}
                              >
                                {user.username}
                              </span>
                              {isPinned ? (
                                <Badge variant="brand" size="xs">
                                  Pinned
                                </Badge>
                              ) : isActiveRow ? (
                                <Badge variant="info" size="xs">
                                  Preview
                                </Badge>
                              ) : null}
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className={cn(isActiveRow && "text-white")}>
                              {user.full_name}
                            </span>
                          </TableCell>
                          <TableCell className={cn(isActiveRow && "text-surface-200")}>
                            {user.email}
                          </TableCell>
                          <TableCell align="center">
                            <Badge variant={getRoleVariant(user.role)} size="sm">
                              {user.role}
                            </Badge>
                          </TableCell>
                          <TableCell align="center">
                            {user.is_active ? (
                              <CheckCircle className="mx-auto h-4 w-4 text-green-500" />
                            ) : (
                              <XCircle className="mx-auto h-4 w-4 text-red-400" />
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Badge variant={SEVERITY_STYLES[review.severity].badge} size="sm">
                              {review.label}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center justify-between gap-3">
                              <span>
                                {user.last_login ? formatDateTime(user.last_login) : "No sign-in yet"}
                              </span>
                              <span
                                className={cn(
                                  "text-[10px] font-semibold uppercase tracking-[0.22em]",
                                  isActiveRow ? "text-brand-200" : "text-surface-500",
                                )}
                              >
                                {isPinned ? "Pinned" : "Inspect"}
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </Card>
          </div>
        )}
      </TabPanel>

      <TabPanel tabId="flags" activeTab={activeTab}>
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Enabled gates" value={enabledFlags} color="green" />
            <StatCard label="Disabled gates" value={FEATURE_FLAGS.length - enabledFlags} color="amber" />
            <StatCard label="Total gates" value={FEATURE_FLAGS.length} color="blue" />
          </div>

          <Card tone="strong">
            <CardHeader
              title="Frontend feature gates"
              description="Environment-controlled switches that decide which premium surfaces are exposed."
            />
            <CardBody>
              <div className="space-y-4">
                {FEATURE_FLAGS.map((flag) => {
                  const value = import.meta.env[flag.key as keyof ImportMetaEnv];
                  const enabled = value === "true";

                  return (
                    <div
                      key={flag.key}
                      className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/5 px-4 py-4"
                    >
                      <div>
                        <p className="text-sm font-medium text-white">{flag.label}</p>
                        <p className="mt-1 text-xs text-surface-400">{flag.description}</p>
                        <p className="mt-2 font-mono text-[10px] text-surface-500">{flag.key}</p>
                      </div>
                      <Badge variant={enabled ? "success" : "neutral"} dot>
                        {enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            </CardBody>
          </Card>
        </div>
      </TabPanel>
    </div>
  );
}

function getRoleVariant(role: string): "brand" | "info" | "neutral" {
  if (role === "admin") return "brand";
  if (role === "analyst") return "info";
  return "neutral";
}

function getReviewCue(
  user: UserRecord,
  severity: Severity,
) {
  if (!user.last_login) return "First login";
  if (!user.is_active) return "Confirm disable";
  if (severity === "watch") return "Check access";
  return "No action";
}
