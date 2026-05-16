import client from '@/api/client'
import type { User, UserRoleGrantAuditRecordList, UserRoleGrantPolicy, UserRoleGrantSummary } from '@/types/auth'

export interface UserCreatePayload {
  username: string
  password: string
  full_name: string
  email: string
  role: string
}

export interface UserUpdatePayload {
  full_name?: string
  email?: string
  role?: string
  is_active?: boolean
}

export interface UserProfileUpdatePayload {
  full_name?: string
  email?: string
}

export interface UserRoleGrantUpdatePayload {
  roles: string[]
  reason?: string
}

export const userApi = {
  async updateMe(payload: UserProfileUpdatePayload): Promise<User> {
    const { data } = await client.patch<User>('/users/me', payload)
    return data
  },

  async create(payload: UserCreatePayload): Promise<User> {
    const { data } = await client.post<User>('/users', payload)
    return data
  },

  async update(userId: number, payload: UserUpdatePayload): Promise<User> {
    const { data } = await client.patch<User>(`/users/${userId}`, payload)
    return data
  },

  async getRoleGrants(userId: number): Promise<UserRoleGrantSummary> {
    const { data } = await client.get<UserRoleGrantSummary>(`/users/${userId}/role-grants`)
    return data
  },

  async getRoleGrantPolicy(): Promise<UserRoleGrantPolicy> {
    const { data } = await client.get<UserRoleGrantPolicy>('/users/role-grants/policy')
    return data
  },

  async getRoleGrantAuditRecords(userId: number): Promise<UserRoleGrantAuditRecordList> {
    const { data } = await client.get<UserRoleGrantAuditRecordList>(`/users/${userId}/role-grants/audit-records`, {
      params: { limit: 10 },
    })
    return data
  },

  async replaceRoleGrants(userId: number, payload: UserRoleGrantUpdatePayload): Promise<UserRoleGrantSummary> {
    const { data } = await client.put<UserRoleGrantSummary>(`/users/${userId}/role-grants`, payload)
    return data
  },

  async deactivate(userId: number): Promise<void> {
    await client.delete(`/users/${userId}`)
  },

  async resetPassword(userId: number, newPassword: string): Promise<void> {
    await client.post(`/users/${userId}/reset-password`, {
      new_password: newPassword,
    })
  },
}
