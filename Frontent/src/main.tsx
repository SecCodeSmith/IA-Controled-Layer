import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { SignIn } from './pages/SignIn'
import { Chat } from './pages/Chat'
import { LiveFeed } from './pages/LiveFeed'
import { AuditLog } from './pages/AuditLog'
import { CallDetail } from './pages/CallDetail'
import { Policy } from './pages/Policy'
import { Reports } from './pages/Reports'
import './index.css'

const queryClient = new QueryClient()

const router = createBrowserRouter([
  { path: '/', element: <SignIn /> },
  { path: '/chat', element: <Chat /> },
  { path: '/admin', element: <LiveFeed /> },
  { path: '/admin/audit', element: <AuditLog /> },
  { path: '/admin/audit/:callId', element: <CallDetail /> },
  { path: '/admin/policy', element: <Policy /> },
  { path: '/admin/reports', element: <Reports /> },
])

async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS !== 'true') return
  const { worker } = await import('./test/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })
}

function renderApp(): void {
  const container = document.getElementById('root')
  if (!container) throw new Error('Root element not found')

  createRoot(container).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
}

void enableMocking().then(renderApp)
