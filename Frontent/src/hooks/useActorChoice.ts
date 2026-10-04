import { useState } from 'react'
import { useDemoUsers } from '../api/auth'
import type { DemoUser } from '../types/identity'

export function useActorChoice(): { users: DemoUser[]; actor: string; setActor: (actor: string) => void } {
  const users = useDemoUsers().data?.users ?? []
  const [selected, setSelected] = useState('')
  return { users, actor: selected || users[0]?.sub || '', setActor: setSelected }
}
