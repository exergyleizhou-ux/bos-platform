import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";

import { BOSAuthShell } from "@/components/auth/BOSAuthShell";
import { ImmersiveLoginScene } from "@/components/auth/ImmersiveLoginScene";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/providers/I18nProvider";
import { useAuthStore } from "@/store/authStore";
import { useUIStore } from "@/store/uiStore";

type LoginFormData = {
  username: string;
  password: string;
};

type ImmersiveMode = "normal" | "entering" | "immersive" | "exiting";

type LoginCopy = {
  localeLabel: string;
  systemName: string;
  systemTagline: string;
  backgroundWordmark: string;
  panelTitle: string;
  panelSubtitle: string;
  panelHelper: string;
  username: string;
  password: string;
  usernameRequired: string;
  passwordRequired: string;
  usernamePlaceholder: string;
  passwordPlaceholder: string;
  showPassword: string;
  hidePassword: string;
  submit: string;
  sso: string;
  forgotPassword: string;
  requestAccess: string;
  entering: string;
  statusItems: string[];
  footerLeft: string;
  footerRight: string;
  operatorStatus: string;
  secureChannel: string;
};

const LOGIN_ENTRY_DURATION_MS = 2100;
const IMMERSIVE_ENTER_DURATION_MS = 1200;
const IMMERSIVE_EXIT_DURATION_MS = 820;

const LOGIN_COPY: Record<"en-US" | "zh-CN", LoginCopy> = {
  "en-US": {
    localeLabel: "EN / 中文",
    systemName: "BOS Code",
    systemTagline: "Biological Operating System",
    backgroundWordmark: "Intelligent Bioconversion",
    panelTitle: "Enter Quietly",
    panelSubtitle: "Access the BOS Code workspace",
    panelHelper: "Authenticate through the live reactor bus and enter the BOS Code workspace.",
    username: "Username / Operator ID",
    password: "Password / Secure Key",
    usernameRequired: "Please enter your username",
    passwordRequired: "Please enter your password",
    usernamePlaceholder: "Type operator id...",
    passwordPlaceholder: "••••••••",
    showPassword: "Show password",
    hidePassword: "Hide password",
    submit: "Enter Workspace",
    sso: "Continue with SSO",
    forgotPassword: "Forgot password",
    requestAccess: "Request access",
    entering: "BOS is coming online...",
    statusItems: ["Tenant-Isolated", "Auditable", "Role-Based Access", "TLS 1.3 Secure Session"],
    footerLeft: "Evidence chain",
    footerRight: "Mainland-ready",
    operatorStatus: "Operator link active",
    secureChannel: "Secure reactor channel",
  },
  "zh-CN": {
    localeLabel: "EN / 中文",
    systemName: "BOS Code",
    systemTagline: "生物操作系统",
    backgroundWordmark: "智能生物转化",
    panelTitle: "安静进入",
    panelSubtitle: "进入 BOS Code 工作台",
    panelHelper: "通过活体反应堆总线完成认证并进入 BOS Code 工作区。",
    username: "用户名 / Operator ID",
    password: "密码 / Secure Key",
    usernameRequired: "请输入用户名",
    passwordRequired: "请输入密码",
    usernamePlaceholder: "输入操作员 ID...",
    passwordPlaceholder: "••••••••",
    showPassword: "显示密码",
    hidePassword: "隐藏密码",
    submit: "进入工作台",
    sso: "使用 SSO 继续",
    forgotPassword: "忘记密码",
    requestAccess: "申请访问",
    entering: "BOS 正在响应...",
    statusItems: ["租户隔离", "可审计", "基于角色访问", "TLS 1.3 安全会话"],
    footerLeft: "证据链路",
    footerRight: "中国大陆就绪",
    operatorStatus: "操作员链路已激活",
    secureChannel: "安全反应堆通道",
  },
};

function createLoginSchema(copy: LoginCopy) {
  return z.object({
    username: z.string().min(1, copy.usernameRequired),
    password: z.string().min(1, copy.passwordRequired),
  });
}

export function LoginForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { locale, toggleLocale } = useI18n();
  const login = useAuthStore((state) => state.login);
  const authError = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const setLoginTransitionActive = useUIStore((state) => state.setLoginTransitionActive);
  const triggerAssistantArrivalBurst = useUIStore((state) => state.triggerAssistantArrivalBurst);
  const loginCameraAutoStart = useUIStore((state) => state.loginCameraAutoStart);
  const setLoginCameraAutoStart = useUIStore((state) => state.setLoginCameraAutoStart);
  const loginGestureGuideCollapsed = useUIStore((state) => state.loginGestureGuideCollapsed);
  const toggleLoginGestureGuideCollapsed = useUIStore(
    (state) => state.toggleLoginGestureGuideCollapsed,
  );

  const [showPassword, setShowPassword] = useState(false);
  const [entryState, setEntryState] = useState<"idle" | "breathing">("idle");
  const [immersiveMode, setImmersiveMode] = useState<ImmersiveMode>("normal");
  const [reducedMotion, setReducedMotion] = useState(() =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  const from = (location.state as { from?: string })?.from ?? "/bos";
  const copy = LOGIN_COPY[locale];
  const loginSchema = createLoginSchema(copy);
  const isEntering = entryState === "breathing";
  const isImmersiveActive = immersiveMode !== "normal";

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  const isBusy = form.formState.isSubmitting || isEntering;
  const username = form.watch("username");
  const password = form.watch("password");
  const formReady = username.trim().length > 0 && password.trim().length > 0;

  useEffect(
    () => () => {
      setLoginTransitionActive(false);
    },
    [setLoginTransitionActive],
  );

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = () => {
      setReducedMotion(media.matches);
    };
    handleChange();
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const submitLogin = form.handleSubmit(async (data) => {
    clearError();

    try {
      await login(data);
      setLoginTransitionActive(true);
      triggerAssistantArrivalBurst(0.96);
      setEntryState("breathing");
      await new Promise((resolve) => window.setTimeout(resolve, LOGIN_ENTRY_DURATION_MS));
      navigate(from, { replace: true });
    } catch {
      setEntryState("idle");
      setLoginTransitionActive(false);
    }
  });

  const handleGestureTogglePassword = () => {
    if (isBusy) return;
    setShowPassword((value) => !value);
  };

  const handleGestureClearField = (target: "username" | "password") => {
    if (isBusy) return;
    form.setValue(target, "", { shouldDirty: true, shouldValidate: true });
    if (target === "password") {
      setShowPassword(false);
    }
    void form.trigger(target);
  };

  const handleGestureClearAll = () => {
    if (isBusy) return;
    form.reset({ username: "", password: "" });
    setShowPassword(false);
    clearError();
  };

  const enterImmersiveMode = () => {
    if (isBusy || immersiveMode !== "normal") return;
    setImmersiveMode("entering");
    window.setTimeout(() => {
      setImmersiveMode((current) => (current === "entering" ? "immersive" : current));
    }, IMMERSIVE_ENTER_DURATION_MS);
  };

  const exitImmersiveMode = () => {
    if (isBusy || immersiveMode === "normal" || immersiveMode === "exiting") return;
    setImmersiveMode("exiting");
    window.setTimeout(() => {
      setImmersiveMode("normal");
    }, IMMERSIVE_EXIT_DURATION_MS);
  };

  return (
    <BOSAuthShell
      localeLabel={copy.localeLabel}
      onToggleLocale={toggleLocale}
      toggleDisabled={isBusy}
      systemName={copy.systemName}
      systemTagline={copy.systemTagline}
      backgroundWordmark={copy.backgroundWordmark}
      statusItems={copy.statusItems}
      immersiveState={immersiveMode}
      sceneOverlay={
        <ImmersiveLoginScene
          entering={isEntering}
          immersiveState={immersiveMode}
          reducedMotion={reducedMotion}
          autoStartCamera={loginCameraAutoStart}
          onAutoStartCameraChange={setLoginCameraAutoStart}
          guideCollapsed={loginGestureGuideCollapsed}
          onToggleGuide={toggleLoginGestureGuideCollapsed}
          onTogglePassword={handleGestureTogglePassword}
          onToggleLocale={toggleLocale}
          onClearField={handleGestureClearField}
          onClearAll={handleGestureClearAll}
          onEnterImmersive={enterImmersiveMode}
          onExitImmersive={exitImmersiveMode}
          onSubmitGesture={() => {
            if (!isBusy) {
              void submitLogin();
            }
          }}
          formReady={formReady}
        />
      }
    >
      <section
        className={`bos-auth-card bos-auth-card--interactive ${isEntering ? "is-entering" : ""} ${
          isImmersiveActive ? "is-mini-mode" : ""
        }`}
        onClick={immersiveMode === "immersive" ? exitImmersiveMode : undefined}
      >
        <div className="bos-auth-card__frame" />
        <div className="bos-auth-card__status-bar" aria-hidden="true">
          <div className="bos-auth-card__status-group">
            <span className="bos-auth-card__status-dot" />
            <span>SYSTEM ONLINE</span>
          </div>
          <span>NEURAL AUTH</span>
        </div>

        <div className="bos-auth-card__copy">
          <div className="bos-auth-card__eyebrow">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>{copy.operatorStatus}</span>
          </div>
          <h2 className="bos-auth-card__title">{copy.panelTitle}</h2>
          <p className="bos-auth-card__subtitle">{copy.panelSubtitle}</p>
          <p className="bos-auth-card__helper">{copy.panelHelper}</p>
        </div>

        <form onSubmit={submitLogin} className="bos-auth-card__form" noValidate>
          {authError ? (
            <div className="bos-auth-card__error" role="alert">
              {authError}
            </div>
          ) : null}

          <div className="bos-auth-card__field" data-login-target="username">
            <div className="bos-auth-card__field-head">
              <label htmlFor="login-username">{copy.username}</label>
              <span>{copy.secureChannel}</span>
            </div>
            <input
              id="login-username"
              autoComplete="username"
              disabled={isBusy}
              className="bos-auth-card__field-input"
              placeholder={copy.usernamePlaceholder}
              {...form.register("username")}
            />
            <span className="bos-auth-card__scan-line" aria-hidden="true" />
            <span className="bos-auth-card__glow-line" aria-hidden="true" />
            {form.formState.errors.username?.message ? (
              <p className="bos-auth-card__field-error">{form.formState.errors.username.message}</p>
            ) : null}
          </div>

          <div className="bos-auth-card__field" data-login-target="password">
            <div className="bos-auth-card__field-head">
              <label htmlFor="login-password">{copy.password}</label>
              <button
                type="button"
                className="bos-auth-card__visibility"
                data-login-target="toggle-password"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? copy.hidePassword : copy.showPassword}
                disabled={isBusy}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              disabled={isBusy}
              className="bos-auth-card__field-input"
              placeholder={copy.passwordPlaceholder}
              {...form.register("password")}
            />
            <span className="bos-auth-card__scan-line" aria-hidden="true" />
            <span className="bos-auth-card__glow-line" aria-hidden="true" />
            {form.formState.errors.password?.message ? (
              <p className="bos-auth-card__field-error">{form.formState.errors.password.message}</p>
            ) : null}
          </div>

          <div className="bos-auth-card__actions">
            <Button
              type="submit"
              fullWidth
              loading={isBusy}
              rightIcon={<ArrowRight className="h-4 w-4" />}
              className="bos-auth-card__primary"
              data-login-target="submit"
            >
              {isEntering ? copy.entering : copy.submit}
            </Button>

            <Button
              type="button"
              variant="outline"
              size="lg"
              fullWidth
              className="bos-auth-card__secondary"
            >
              {copy.sso}
            </Button>
          </div>

          <div className="bos-auth-card__links">
            <a
              href="mailto:security@bos-code.local?subject=Reset%20BOS%20Code%20password"
              className="bos-auth-card__link"
            >
              {copy.forgotPassword}
            </a>
            <a
              href="mailto:access@bos-code.local?subject=Request%20BOS%20Code%20access"
              className="bos-auth-card__link"
            >
              {copy.requestAccess}
            </a>
          </div>
        </form>

        <div className="bos-auth-card__footer">
          <span>{copy.footerLeft}</span>
          <span>{copy.footerRight}</span>
        </div>
      </section>
    </BOSAuthShell>
  );
}
