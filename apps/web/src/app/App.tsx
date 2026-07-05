import { type FormEvent, useEffect, useState } from "react";
import { Bot, Globe2, KeyRound, LockKeyhole, PawPrint, UserRound, X } from "lucide-react";

import ChannelWatchLogo from "../features/codium/CodiumLogo";
import RobotScene, { type MascotVariant } from "../features/codium/RobotScene";
import {
  AUTH_EXPIRED_EVENT,
  type AuthBootstrap,
  type AuthUser,
  clearAuthSession,
  fetchAuthBootstrap,
  getStoredAuthUser,
  login,
  logout,
  saveAuthSession,
} from "../shared/api/auth";
import { RadarApp } from "./RadarApp";

type Locale = "zh" | "en";

const mascotOptions = [
  { id: "robot", icon: Bot, label: "机器人" },
  { id: "fox", icon: PawPrint, label: "小狐狸" },
] satisfies { id: MascotVariant; icon: typeof Bot; label: string }[];

export function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredAuthUser());
  const [bootstrap, setBootstrap] = useState<AuthBootstrap | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [bootMessage, setBootMessage] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [locale, setLocale] = useState<Locale>("zh");
  const [mascot, setMascot] = useState<MascotVariant>("robot");

  useEffect(() => {
    let isMounted = true;
    fetchAuthBootstrap()
      .then((payload) => {
        if (!isMounted) return;
        setBootstrap(payload);
        if (payload.authenticated && payload.user) {
          setUser(payload.user);
        } else {
          clearAuthSession();
          setUser(null);
        }
      })
      .catch((error) => {
        if (!isMounted) return;
        setBootMessage(`后端连接失败：${(error as Error).message}`);
        setUser(null);
      })
      .finally(() => {
        if (isMounted) setIsChecking(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  async function handleLogin(username: string, password: string) {
    const session = await login(username, password);
    saveAuthSession(session);
    setUser(session.user);
    setAuthOpen(false);
    setBootMessage("");
  }

  async function handleLogout() {
    await logout();
    clearAuthSession();
    setUser(null);
  }

  if (user) {
    return <RadarApp user={user} onLogout={handleLogout} />;
  }

  const languageCode = locale === "zh" ? "ZH" : "EN";
  const heroMode = authOpen ? "auth" : "intro";

  return (
    <main className={`codium-shell ${authOpen ? "is-auth" : ""}`}>
      <RobotScene mode={heroMode} mascot={mascot} />

      <header className="codium-topbar" aria-label="站点导航">
        <a className="codium-brand-mark" href="#" aria-label="Channel Watch 首页" onClick={(event) => event.preventDefault()}>
          <span className="codium-logo-core">
            <ChannelWatchLogo className="codium-logo" />
          </span>
          <span>
            <strong>Channel Watch</strong>
            <small>AI GATEWAY WATCH</small>
          </span>
        </a>

        <div className="codium-top-actions">
          <div className="codium-mascot-switch" aria-label="3D 角色切换">
            {mascotOptions.map(({ id, icon: Icon, label }) => (
              <button className={mascot === id ? "is-active" : ""} type="button" key={id} onClick={() => setMascot(id)} aria-pressed={mascot === id} title={label}>
                <Icon size={16} />
                <span>{label}</span>
              </button>
            ))}
          </div>
          <button className="codium-icon-pill" type="button" onClick={() => setLocale((value) => (value === "zh" ? "en" : "zh"))} aria-label="切换语言">
            <Globe2 size={17} />
            <span>{languageCode}</span>
          </button>
        </div>
      </header>

      <section className={`codium-hero-grid ${authOpen ? "is-auth" : ""}`} aria-label="Channel Watch">
        {authOpen ? (
          <ChannelWatchLoginPanel bootstrap={bootstrap} message={bootMessage} isChecking={isChecking} onClose={() => setAuthOpen(false)} onLogin={handleLogin} />
        ) : (
          <div className="codium-hero-copy">
            <h1>Channel Watch</h1>
            <p className="codium-tagline">看住每条渠道，让调度始终有据可依。</p>
            <p className="codium-hero-description">
              持续探测渠道、分组与 Key 的健康状态，自动记录异常、模型检测结果和倍率变化。账号异常时及时熔断隔离，冷却期持续复查，恢复后再回到可调度队列。
            </p>
            <p className="codium-hero-emphasis">渠道监控、Key 健康、模型探测、倍率同步、告警追踪。</p>

            <div className="codium-hero-actions" aria-label="账户操作">
              <button className="codium-primary-button" type="button" onClick={() => setAuthOpen(true)}>
                <LockKeyhole size={18} />
                登录控制台
              </button>
            </div>
          </div>
        )}
      </section>

      {!authOpen ? (
        <button className="codium-footer-bar" type="button" onClick={() => setAuthOpen(true)}>
          <span>{isChecking ? "正在检查登录状态" : "进入渠道监控台"}</span>
        </button>
      ) : null}
    </main>
  );
}

function ChannelWatchLoginPanel({
  bootstrap,
  message,
  isChecking,
  onClose,
  onLogin,
}: {
  bootstrap: AuthBootstrap | null;
  message: string;
  isChecking: boolean;
  onClose: () => void;
  onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState(bootstrap?.username || "admin");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success">("idle");
  const [error, setError] = useState("");
  const isLoading = status === "loading";
  const passwordFile = bootstrap?.password_file || "data/admin-password.txt";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("loading");
    try {
      await onLogin(username.trim(), password);
      setStatus("success");
    } catch (loginError) {
      setStatus("idle");
      setError(loginError instanceof Error ? loginError.message : "登录失败，请稍后重试");
    }
  }

  return (
    <aside className="codium-auth-panel" aria-label="登录">
      <button className="codium-close-button" type="button" onClick={onClose} aria-label="关闭登录">
        <X size={18} />
      </button>
      <span className="codium-auth-kicker">Secure Access</span>
      <h2>登录</h2>
      <p>使用默认管理员账号进入渠道监控控制台。</p>

      <form className="codium-auth-form" onSubmit={handleSubmit}>
        <label className="codium-field">
          <span>账号</span>
          <div className="codium-input-shell">
            <UserRound size={18} />
            <input type="text" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required disabled={isLoading || isChecking} />
          </div>
        </label>

        <label className="codium-field">
          <span>密码</span>
          <div className="codium-input-shell">
            <KeyRound size={18} />
            <input
              type="password"
              placeholder="输入自动生成的管理员密码"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              disabled={isLoading || isChecking}
            />
          </div>
        </label>

        {message ? <p className="codium-auth-error" role="alert">{message}</p> : null}
        {error ? <p className="codium-auth-error" role="alert">{error}</p> : null}
        {status === "success" ? <p className="codium-auth-success">登录成功</p> : null}

        <button className="codium-submit-button" type="submit" disabled={isLoading || isChecking}>
          {isLoading ? "登录中..." : "登录"}
        </button>
      </form>

      <p className="codium-login-note">默认账号 admin，密码文件：{passwordFile}</p>
    </aside>
  );
}
