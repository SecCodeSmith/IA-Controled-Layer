import type { ComponentType, ReactNode } from 'react'
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ElementProps {
  node?: ExtraProps['node']
  className?: string
  children?: ReactNode
}

// Wraps an intrinsic element with fixed Tailwind classes and drops react-markdown's `node` prop.
function styled(Tag: keyof React.JSX.IntrinsicElements, classes: string): ComponentType<ElementProps> {
  const Component = Tag as unknown as ComponentType<ElementProps>
  return function StyledElement({ node, className, ...rest }: ElementProps) {
    void node
    return <Component {...rest} className={className ? `${classes} ${className}` : classes} />
  }
}

const Table = styled('table', 'w-full border-collapse text-left text-sm')

const components: Components = {
  h1: styled('h1', 'mb-3 mt-6 text-2xl font-semibold tracking-tight first:mt-0'),
  h2: styled('h2', 'mb-2 mt-6 text-xl font-semibold tracking-tight first:mt-0'),
  h3: styled('h3', 'mb-2 mt-5 text-base font-semibold first:mt-0'),
  p: styled('p', 'my-3 text-sm leading-relaxed'),
  ul: styled('ul', 'my-3 list-disc pl-6 text-sm leading-relaxed'),
  ol: styled('ol', 'my-3 list-decimal pl-6 text-sm leading-relaxed'),
  li: styled('li', 'my-1'),
  table: ({ node, children }) => {
    void node
    return (
      <div className="my-4 overflow-x-auto">
        <Table>{children}</Table>
      </div>
    )
  },
  thead: styled('thead', 'bg-[#F4F5F2]'),
  tr: styled('tr', 'even:bg-[#FAFAF8]'),
  th: styled('th', 'border border-border px-3 py-2 font-semibold'),
  td: styled('td', 'border border-border px-3 py-2'),
  code: styled('code', 'rounded bg-[#F4F5F2] px-1 py-0.5 font-mono text-[13px]'),
  pre: styled(
    'pre',
    'my-4 overflow-x-auto rounded-lg bg-[#F4F5F2] px-4 py-3.5 font-mono text-[13px] leading-relaxed [&>code]:bg-transparent [&>code]:p-0',
  ),
  blockquote: styled('blockquote', 'my-4 border-l-4 border-border pl-4 text-sm italic text-muted'),
  a: ({ node, href, children }) => {
    void node
    return (
      <a href={href} target="_blank" rel="noreferrer" className="underline">
        {children}
      </a>
    )
  },
  hr: ({ node }) => {
    void node
    return <hr className="my-6 border-border" />
  },
}

export function MarkdownView({ markdown }: { markdown: string }) {
  return (
    <div className="px-5 py-4">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
