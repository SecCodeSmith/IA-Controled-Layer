import { avatarColorFor } from '../../lib/colors'

interface AvatarProps {
  sub: string
  initials: string
  size?: number
}

export function Avatar({ sub, initials, size = 44 }: AvatarProps) {
  const colors = avatarColorFor(sub)
  return (
    <span
      className="flex items-center justify-center rounded-full font-semibold"
      style={{
        width: size,
        height: size,
        background: colors.bg,
        color: colors.fg,
        fontSize: size <= 36 ? 14 : 16,
      }}
    >
      {initials}
    </span>
  )
}
