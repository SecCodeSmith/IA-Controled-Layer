import { useMutation, useQuery } from '@tanstack/react-query'
import { publicApi } from './client'
import type { AuthTokenResponse, AuthUsersResponse } from '../types/identity'

export function useDemoUsers() {
  return useQuery({
    queryKey: ['auth', 'users'],
    queryFn: () => publicApi.get<AuthUsersResponse>('/auth/users'),
  })
}

export function useSignIn() {
  return useMutation({
    mutationFn: (sub: string) => publicApi.post<AuthTokenResponse>('/auth/token', { sub }),
  })
}
