export type PreBlockTone = 'default' | 'danger' | 'success'

const TONE_STYLES: Record<PreBlockTone, { background: string; border?: string }> = {
  default: { background: '#F4F5F2' },
  danger: { background: '#FDF3F0', border: '1px solid #FADFD7' },
  success: { background: '#F2F8F4', border: '1px solid #E2F0E8' },
}

export function PreBlock({ children, tone = 'default' }: { children: string; tone?: PreBlockTone }) {
  return (
    <pre
      className="m-0 overflow-x-auto rounded-lg px-4 py-3.5 font-mono text-[13px] leading-relaxed"
      style={TONE_STYLES[tone]}
    >
      {children}
    </pre>
  )
}
