import { Link, useNavigate } from 'react-router-dom'
import { useDemoUsers, useSignIn } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import { Avatar } from '../components/common/Avatar'
import { ShieldLogo } from '../components/common/ShieldLogo'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { errorMessage } from '../lib/errorMessage'
import { roleLabel } from '../lib/roleLabel'
import type { DemoUser } from '../types/identity'

export function SignIn() {
  const { data, isLoading, isError, error } = useDemoUsers()
  const signIn = useSignIn()
  const auth = useAuth()
  const navigate = useNavigate()

  async function handleSelect(user: DemoUser) {
    const response = await signIn.mutateAsync(user.sub)
    auth.signIn({ token: response.access_token, identity: response.claims })
    navigate('/chat')
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-7 px-5 py-12">
      <div className="flex w-full max-w-[560px] flex-col gap-7">
        <div className="flex items-center gap-3">
          <ShieldLogo size={32} color="#2348B8" />
          <span className="text-[22px] font-semibold tracking-tight">Control Layer</span>
        </div>
        <div className="flex flex-col gap-2">
          <h1 className="m-0 text-[34px] font-semibold leading-tight tracking-tight">
            Sign in to your agent
          </h1>
          <p className="m-0 text-base leading-relaxed text-muted">
            Choose a demo user. Role and location come from the SSO token and set which tools the
            agent receives.
          </p>
        </div>

        {isLoading ? <Spinner label="Loading demo users…" /> : null}
        {isError ? <ErrorBanner message={errorMessage(error)} /> : null}
        {signIn.isError ? <ErrorBanner message={errorMessage(signIn.error)} /> : null}

        <div className="flex flex-col gap-3">
          {data?.users.map((user) => (
            <button
              key={user.sub}
              type="button"
              onClick={() => void handleSelect(user)}
              disabled={signIn.isPending}
              className="flex items-center justify-between gap-4 rounded-[10px] border border-border bg-white px-5 py-4.5 text-left text-ink hover:border-accent disabled:opacity-60"
            >
              <span className="flex items-center gap-3.5">
                <Avatar sub={user.sub} initials={user.initials} />
                <span className="flex flex-col gap-0.5">
                  <span className="text-[17px] font-semibold">{user.name}</span>
                  <span className="text-sm text-muted">
                    {roleLabel(user.role)} · {user.location}
                  </span>
                </span>
              </span>
              <span className="font-mono text-[13px] text-accent">
                {user.mcp_servers.length} MCP servers
              </span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap justify-between gap-3 border-t border-border pt-2 text-sm text-muted">
          <span>Identity provider: mock SSO (OIDC)</span>
          <Link to="/admin">Open admin dashboard</Link>
        </div>
      </div>
    </div>
  )
}
