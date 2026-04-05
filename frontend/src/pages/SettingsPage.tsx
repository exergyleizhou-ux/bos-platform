import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye,
  Lock,
  Monitor,
  Moon,
  Palette,
  Save,
  Sun,
  User,
} from "lucide-react";
import toast from "react-hot-toast";

import { useAuthStore } from "@/store/authStore";
import { useTheme } from "@/providers/ThemeProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardFooter, CardHeader, StatCard } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { getRoleLabel } from "@/types/auth";
import { cn } from "@/lib/utils";

const profileSchema = z.object({
  full_name: z.string().min(1, "Name is required").max(100),
  email: z.string().email("Invalid email"),
});

type ProfileFormData = z.infer<typeof profileSchema>;

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(8, "Min 8 characters"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

type PasswordFormData = z.infer<typeof passwordSchema>;
type ThemeOption = "light" | "dark" | "system";
type PreviewMode = "light" | "dark";

const THEME_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

const THEME_SURFACES: Array<{
  value: ThemeOption;
  label: string;
  description: string;
  icon: typeof Sun;
}> = [
  {
    value: "dark",
    label: "Dark console",
    description: "Default operator surface with the strongest hierarchy and reduced glare.",
    icon: Moon,
  },
  {
    value: "light",
    label: "Light console",
    description: "High-clarity alternative for bright workspaces and review sessions.",
    icon: Sun,
  },
  {
    value: "system",
    label: "Follow system",
    description: "Let the console inherit the workstation preference automatically.",
    icon: Monitor,
  },
];

const PREVIEW_MODULES = [
  {
    label: "SER",
    darkTone: "bg-emerald-500/18",
    lightTone: "bg-emerald-100",
  },
  {
    label: "Queue",
    darkTone: "bg-sky-500/18",
    lightTone: "bg-sky-100",
  },
  {
    label: "Twins",
    darkTone: "bg-amber-500/18",
    lightTone: "bg-amber-100",
  },
] as const;

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user);
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState("profile");

  const tabs = [
    { id: "profile", label: "Profile", icon: <User className="h-4 w-4" /> },
    { id: "password", label: "Access", icon: <Lock className="h-4 w-4" /> },
    { id: "preferences", label: "Console", icon: <Palette className="h-4 w-4" /> },
  ];

  const profileForm = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name ?? "",
      email: user?.email ?? "",
    },
  });

  const passwordForm = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const activeThemeCard = useMemo(
    () => THEME_SURFACES.find((item) => item.value === theme) ?? THEME_SURFACES[0],
    [theme],
  );

  const previewMode: PreviewMode = theme === "system" ? resolvedTheme : theme;

  const onProfileSubmit = async (data: ProfileFormData) => {
    try {
      const { default: client } = await import("@/api/client");
      await client.patch("/users/me", data);
      toast.success("Profile updated");
    } catch {
      toast.error("Failed to update profile");
    }
  };

  const onPasswordSubmit = async (data: PasswordFormData) => {
    try {
      const { default: client } = await import("@/api/client");
      await client.post("/users/me/change-password", {
        current_password: data.current_password,
        new_password: data.new_password,
      });
      toast.success("Password changed");
      passwordForm.reset();
    } catch {
      toast.error("Failed to change password");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="Operator identity and console preferences"
        description="Tune the operator profile, access posture, and presentation defaults that shape this premium control surface."
        badges={[
          { label: getRoleLabel(user?.role ?? "viewer"), variant: "info" },
          {
            label: user?.is_active ? "Account active" : "Account restricted",
            variant: user?.is_active ? "success" : "warning",
          },
          { label: `Theme: ${theme}`, variant: "brand" },
        ]}
        stats={[
          {
            label: "Username",
            value: user?.username ?? "Unknown",
            hint: "Current operator handle",
          },
          {
            label: "Role",
            value: getRoleLabel(user?.role ?? "viewer"),
            hint: "Permission envelope currently in force",
          },
          {
            label: "Account state",
            value: user?.is_active ? "Enabled" : "Restricted",
            hint: "Whether this operator can act inside the console",
          },
          {
            label: "Render mode",
            value: resolvedTheme,
            hint: "Theme mode after system resolution",
          },
        ]}
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      <TabPanel tabId="profile" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card tone="strong">
            <CardHeader
              title="Profile identity"
              description="Update the operator name and contact address shown across the control surface."
            />
            <CardBody>
              <form
                onSubmit={profileForm.handleSubmit(onProfileSubmit)}
                className="space-y-4"
                noValidate
              >
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="metric-kicker">Runtime role</p>
                      <p className="mt-2 text-sm font-medium text-white">
                        {user?.username ?? "Unknown"}
                      </p>
                    </div>
                    <Badge variant="brand">{getRoleLabel(user?.role ?? "viewer")}</Badge>
                  </div>
                </div>

                <Input
                  label="Full Name"
                  required
                  error={profileForm.formState.errors.full_name?.message}
                  {...profileForm.register("full_name")}
                />
                <Input
                  label="Email"
                  type="email"
                  required
                  error={profileForm.formState.errors.email?.message}
                  {...profileForm.register("email")}
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
            <Card>
              <CardHeader
                title="Identity readout"
                description="Fast summary of the current operator footprint."
              />
              <CardBody className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <StatCard label="Display name" value={user?.full_name ?? "Unknown"} color="blue" />
                <StatCard label="Contact" value={user?.email ?? "Not set"} color="neutral" />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Operator notes"
                description="How this page is meant to be used."
              />
              <CardBody className="space-y-3">
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <p className="metric-kicker">Editable here</p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Human-readable identity and email contact used by surrounding surfaces.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <p className="metric-kicker">Not editable here</p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Role assignment and operator activation remain admin-governed controls.
                  </p>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="password" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <Card tone="strong">
            <CardHeader
              title="Credential rotation"
              description="Rotate the operator password without leaving the console."
            />
            <CardBody>
              <form
                onSubmit={passwordForm.handleSubmit(onPasswordSubmit)}
                className="space-y-4"
                noValidate
              >
                <Input
                  label="Current Password"
                  type="password"
                  autoComplete="current-password"
                  required
                  error={passwordForm.formState.errors.current_password?.message}
                  {...passwordForm.register("current_password")}
                />
                <Input
                  label="New Password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={passwordForm.formState.errors.new_password?.message}
                  {...passwordForm.register("new_password")}
                />
                <Input
                  label="Confirm New Password"
                  type="password"
                  autoComplete="new-password"
                  required
                  error={passwordForm.formState.errors.confirm_password?.message}
                  {...passwordForm.register("confirm_password")}
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
            <Card>
              <CardHeader
                title="Access posture"
                description="Current state of the operator account."
              />
              <CardBody className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <StatCard
                  label="Access state"
                  value={user?.is_active ? "Enabled" : "Restricted"}
                  color={user?.is_active ? "green" : "amber"}
                />
                <StatCard
                  label="Role scope"
                  value={getRoleLabel(user?.role ?? "viewer")}
                  color="blue"
                />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Rotation guidance"
                description="Expected operator hygiene for this console."
              />
              <CardBody className="space-y-3">
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <p className="metric-kicker">Minimum bar</p>
                  <p className="mt-2 text-sm text-surface-300">
                    Use at least 8 characters and avoid reusing operator credentials from adjacent systems.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <p className="metric-kicker">When to rotate</p>
                  <p className="mt-2 text-sm text-surface-300">
                    Rotate after shared-workstation use, access handoff, or any suspected credential exposure.
                  </p>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="preferences" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card tone="strong">
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
                  const Icon = item.icon;
                  const active = item.value === theme;

                  return (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setTheme(item.value)}
                      className={cn(
                        "flex items-start gap-4 rounded-2xl border px-4 py-4 text-left transition-all duration-150",
                        active
                          ? "border-brand-400/20 bg-brand-500/15 shadow-glow"
                          : "border-white/8 bg-white/5 hover:border-white/12 hover:bg-white/7",
                      )}
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-200">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="min-w-0">
                        <span className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{item.label}</span>
                          {active ? <Badge variant="brand">Selected</Badge> : null}
                        </span>
                        <span className="mt-2 block text-sm leading-6 text-surface-400">
                          {item.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <ThemeConsolePreview mode={previewMode} />
            </CardBody>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader
                title="Display resolution"
                description="Resolved theme state after applying system logic."
              />
              <CardBody className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <StatCard label="Requested mode" value={theme} color="blue" />
                <StatCard label="Resolved mode" value={resolvedTheme} color="green" />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Operator reading mode"
                description="How the current theme affects the control surface."
              />
              <CardBody className="space-y-3">
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <p className="metric-kicker">Active theme</p>
                  <p className="mt-2 text-sm font-medium text-white">{activeThemeCard.label}</p>
                  <p className="mt-2 text-sm leading-6 text-surface-400">
                    {activeThemeCard.description}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-sky-200" />
                    <p className="text-sm font-medium text-white">Usage note</p>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-surface-400">
                    Dark mode preserves the highest visual contrast in dense analytic views, while light mode can help during document review or bright-room sessions.
                  </p>
                </div>
                {theme === "system" ? (
                  <div className="rounded-2xl border border-sky-400/15 bg-sky-500/10 px-4 py-3 text-sm text-sky-100">
                    System mode is currently resolving to <span className="font-semibold">{resolvedTheme}</span>.
                  </div>
                ) : null}
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>
    </div>
  );
}

function ThemeConsolePreview({ mode }: { mode: PreviewMode }) {
  const isDark = mode === "dark";
  const previewReadouts = isDark
    ? [
        { label: "Contrast", value: "92%", tone: "success" as const },
        { label: "Focus drift", value: "Low", tone: "info" as const },
        { label: "Queue noise", value: "18m", tone: "neutral" as const },
      ]
    : [
        { label: "Contrast", value: "78%", tone: "info" as const },
        { label: "Review mode", value: "Paper", tone: "success" as const },
        { label: "Glare load", value: "Moderate", tone: "warning" as const },
      ];

  return (
    <div className="rounded-[28px] border border-white/10 bg-white/5 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="metric-kicker">Theme preview</p>
          <p className="mt-2 text-sm font-medium text-white">
            {isDark ? "Dark console rendering" : "Light console rendering"}
          </p>
        </div>
        <Badge variant={isDark ? "success" : "info"}>{mode}</Badge>
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
                "rounded-2xl border px-4 py-3",
                isDark ? "border-white/8 bg-white/5" : "border-slate-300/70 bg-white/90",
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <p className={cn("metric-kicker", isDark ? "text-surface-400" : "text-slate-500")}>
                  {readout.label}
                </p>
                <Badge variant={readout.tone} size="xs">
                  Live
                </Badge>
              </div>
              <p className={cn("mt-2 text-base font-semibold", isDark ? "text-white" : "text-slate-900")}>
                {readout.value}
              </p>
            </motion.div>
          ))}
        </div>

        <div
          className={cn(
            "relative overflow-hidden rounded-[24px] border p-4 transition-all duration-200",
            isDark ? "border-white/10 bg-[#08111d]" : "border-slate-300/80 bg-[#f7fafc]",
          )}
        >
          <motion.div
            className={cn(
              "pointer-events-none absolute inset-y-0 left-[-20%] w-[42%] blur-3xl",
              isDark ? "bg-emerald-500/18" : "bg-sky-300/35",
            )}
            animate={{ x: ["-10%", "110%", "-10%"], opacity: [0.16, 0.3, 0.16] }}
            transition={{ duration: 6.2, repeat: Infinity, ease: "easeInOut" }}
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
              <div
                className={cn(
                  "rounded-[20px] border p-4",
                  isDark ? "border-white/8 bg-white/5" : "border-slate-300/70 bg-white/95",
                )}
              >
                <div className="flex items-center gap-2">
                  <motion.span
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-2xl",
                      isDark ? "bg-emerald-500/20" : "bg-emerald-100",
                    )}
                    animate={{ scale: [1, 1.08, 1] }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <motion.span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
                        isDark ? "bg-emerald-200" : "bg-emerald-500",
                      )}
                      animate={{ opacity: [0.6, 1, 0.6] }}
                      transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                    />
                  </motion.span>
                  <div>
                    <div className={cn("h-2.5 w-24 rounded-full", isDark ? "bg-white/80" : "bg-slate-800")} />
                    <div className={cn("mt-2 h-2 w-20 rounded-full", isDark ? "bg-white/20" : "bg-slate-300")} />
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
                        "rounded-2xl border px-3 py-3",
                        item === 0
                          ? isDark
                            ? "border-emerald-400/20 bg-emerald-500/12"
                            : "border-emerald-200 bg-emerald-50"
                          : isDark
                            ? "border-white/8 bg-white/4"
                            : "border-slate-200 bg-slate-50",
                      )}
                    >
                      <motion.div
                        className={cn("h-2.5 rounded-full", isDark ? "bg-white/80" : "bg-slate-800")}
                        animate={{ width: item === 0 ? [72, 84, 72] : [64, 76, 64] }}
                        transition={{ duration: 2.4 + item * 0.2, repeat: Infinity, ease: "easeInOut" }}
                      />
                      <motion.div
                        className={cn("mt-2 h-2 rounded-full", isDark ? "bg-white/15" : "bg-slate-300")}
                        animate={{ width: [92, 106, 92] }}
                        transition={{ duration: 2.8 + item * 0.25, repeat: Infinity, ease: "easeInOut" }}
                      />
                    </motion.div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <div
                  className={cn(
                    "rounded-[20px] border px-4 py-3",
                    isDark ? "border-white/8 bg-white/5" : "border-slate-300/70 bg-white/95",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className={cn("h-2.5 w-28 rounded-full", isDark ? "bg-white/85" : "bg-slate-800")} />
                      <div className={cn("mt-2 h-2 w-40 rounded-full", isDark ? "bg-white/15" : "bg-slate-300")} />
                    </div>
                    <div className="flex gap-2">
                      <motion.span
                        className={cn("h-8 rounded-2xl", isDark ? "bg-white/8" : "bg-slate-100")}
                        animate={{ width: [56, 70, 56] }}
                        transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
                      />
                      <motion.span
                        className={cn("h-8 rounded-2xl", isDark ? "bg-emerald-500/20" : "bg-emerald-100")}
                        animate={{ width: [36, 48, 36] }}
                        transition={{ duration: 1.9, repeat: Infinity, ease: "easeInOut" }}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  {PREVIEW_MODULES.map((item, index) => (
                    <motion.div
                      key={`${mode}-${item.label}`}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 + index * 0.05, duration: 0.2 }}
                      className={cn(
                        "rounded-[20px] border px-4 py-4",
                        isDark ? "border-white/8 bg-white/5" : "border-slate-300/70 bg-white/95",
                      )}
                    >
                      <div className={cn("text-[10px] uppercase tracking-[0.24em]", isDark ? "text-slate-400" : "text-slate-500")}>
                        {item.label}
                      </div>
                      <motion.div
                        className={cn(
                          "mt-3 h-7 origin-left rounded-full",
                          isDark ? item.darkTone : item.lightTone,
                        )}
                        animate={{ scaleX: [0.68, 1, 0.82] }}
                        transition={{ duration: 2 + index * 0.25, repeat: Infinity, ease: "easeInOut" }}
                      />
                    </motion.div>
                  ))}
                </div>

                <div
                  className={cn(
                    "rounded-[20px] border p-4",
                    isDark ? "border-white/8 bg-white/5" : "border-slate-300/70 bg-white/95",
                  )}
                >
                  <div className={cn("h-2.5 w-32 rounded-full", isDark ? "bg-white/85" : "bg-slate-800")} />
                  <div className="mt-4 grid gap-3 sm:grid-cols-[0.58fr_0.42fr]">
                    <div
                      className={cn(
                        "relative overflow-hidden rounded-2xl",
                        isDark ? "bg-white/6" : "bg-slate-100",
                      )}
                      style={{ height: 108 }}
                    >
                      <motion.div
                        className={cn(
                          "absolute bottom-0 left-[10%] w-[14%] rounded-t-2xl",
                          isDark ? "bg-emerald-500/24" : "bg-emerald-200",
                        )}
                        animate={{ height: [30, 64, 38] }}
                        transition={{ duration: 2.3, repeat: Infinity, ease: "easeInOut" }}
                      />
                      <motion.div
                        className={cn(
                          "absolute bottom-0 left-[34%] w-[14%] rounded-t-2xl",
                          isDark ? "bg-sky-500/24" : "bg-sky-200",
                        )}
                        animate={{ height: [54, 82, 60] }}
                        transition={{ duration: 2.1, repeat: Infinity, ease: "easeInOut" }}
                      />
                      <motion.div
                        className={cn(
                          "absolute bottom-0 left-[58%] w-[14%] rounded-t-2xl",
                          isDark ? "bg-amber-500/24" : "bg-amber-200",
                        )}
                        animate={{ height: [42, 74, 50] }}
                        transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
                      />
                    </div>
                    <div className="space-y-3">
                      {[0, 1].map((item) => (
                        <div
                          key={`${mode}-signal-${item}`}
                          className={cn(
                            "rounded-2xl p-3",
                            isDark ? "bg-white/6" : "bg-slate-100",
                          )}
                        >
                          <div className={cn("h-2.5 w-20 rounded-full", isDark ? "bg-white/80" : "bg-slate-800")} />
                          <motion.div
                            className={cn(
                              "mt-3 h-2 rounded-full",
                              isDark ? "bg-white/15" : "bg-slate-300",
                            )}
                            animate={{ width: item === 0 ? [64, 92, 64] : [84, 56, 84] }}
                            transition={{ duration: 2.2 + item * 0.3, repeat: Infinity, ease: "easeInOut" }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
