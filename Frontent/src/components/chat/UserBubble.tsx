export function UserBubble({ text }: { text: string }) {
  return (
    <div className="max-w-[75%] self-end rounded-tl-xl rounded-tr-xl rounded-br-sm rounded-bl-xl bg-accent-soft px-4 py-3 text-[15px] leading-relaxed">
      {text}
    </div>
  )
}
