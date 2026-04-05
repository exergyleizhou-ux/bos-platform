import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowRight,
  Eye,
  EyeOff,
  Leaf,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const authError = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);

  const [showPassword, setShowPassword] = useState(false);

  const from = (location.state as { from?: string })?.from ?? "/dashboard";

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  const onSubmit = async (data: LoginFormData) => {
    clearError();
    try {
      await login(data);
      navigate(from, { replace: true });
    } catch {
      // auth error is persisted in the store for inline display
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[12%] top-[10%] h-72 w-72 rounded-full bg-brand-500/12 blur-3xl" />
        <div className="absolute bottom-[12%] right-[10%] h-96 w-96 rounded-full bg-sky-500/10 blur-3xl" />
      </div>

      <div className="relative z-[1] grid w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="premium-hero hidden min-h-[36rem] rounded-[32px] p-8 lg:flex lg:flex-col lg:justify-between">
          <div className="space-y-6">
            <div className="flex h-14 w-14 items-center justify-center rounded-[22px] border border-brand-400/20 bg-brand-500/15 text-brand-100 shadow-glow">
              <Leaf className="h-7 w-7" />
            </div>
            <div className="space-y-4">
              <Badge variant="info">Premium operator console</Badge>
              <h1 className="max-w-xl text-5xl font-semibold tracking-tight text-white">
                BOS control surface for high-trust release decisions.
              </h1>
              <p className="max-w-xl text-base leading-7 text-surface-300">
                Audit visibility, decision-first workflows, and premium command-center UX for staged bioconversion operations.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-3xl border border-white/10 bg-white/6 p-4">
              <ShieldCheck className="h-5 w-5 text-emerald-200" />
              <p className="mt-4 text-sm font-medium text-white">Audit ready</p>
              <p className="mt-2 text-xs leading-5 text-surface-400">
                Release posture, evidence levels, and provenance stay visible.
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/6 p-4">
              <Sparkles className="h-5 w-5 text-brand-200" />
              <p className="mt-4 text-sm font-medium text-white">Dynamic UI</p>
              <p className="mt-2 text-xs leading-5 text-surface-400">
                Semantic motion and dense operator layouts instead of template dashboards.
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/6 p-4">
              <LockKeyhole className="h-5 w-5 text-sky-200" />
              <p className="mt-4 text-sm font-medium text-white">Role aware</p>
              <p className="mt-2 text-xs leading-5 text-surface-400">
                Protected command surfaces with typed auth and tenant boundaries.
              </p>
            </div>
          </div>
        </section>

        <section className="premium-panel-strong glass-border mx-auto w-full max-w-md p-6 sm:p-8">
          <div className="mb-8 flex flex-col items-center text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-[22px] border border-brand-400/20 bg-brand-500/15 text-brand-100 shadow-glow">
              <Leaf className="h-7 w-7" />
            </div>
            <h1 className="mt-5 text-3xl font-semibold text-white">BOS Pipeline</h1>
            <p className="mt-2 text-sm leading-6 text-surface-400">
              Sign in to the premium operator console.
            </p>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {authError ? (
              <div className="rounded-2xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                {authError}
              </div>
            ) : null}

            <Input
              label="Username"
              autoComplete="username"
              required
              error={form.formState.errors.username?.message}
              {...form.register("username")}
            />

            <Input
              label="Password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              error={form.formState.errors.password?.message}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="text-surface-500 transition-colors hover:text-white"
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              {...form.register("password")}
            />

            <Button
              type="submit"
              fullWidth
              loading={form.formState.isSubmitting}
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              Enter command center
            </Button>
          </form>

          <div className="mt-6 flex items-center justify-between gap-3 text-xs text-surface-500">
            <span>BOS Pipeline v9.0</span>
            <span>Bioconversion Optimization System</span>
          </div>
        </section>
      </div>
    </div>
  );
}
