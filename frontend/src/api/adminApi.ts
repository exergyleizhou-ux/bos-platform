import client from '@/api/client'
import type { User } from '@/types/auth'

export interface HealthStatus {
  status: string
  database: string
  redis: string
  version: string
  uptime_seconds: number
}

export interface SessionRecord {
  username: string
  tenant_id: number
  ip_address: string | null
  user_agent: string | null
  timestamp: string | null
}

export interface FeatureFlagsResponse {
  flags: Record<string, boolean>
  source: string
}

export const adminApi = {
  async getHealth(): Promise<HealthStatus> {
    const [{ data: live }, { data: ready }] = await Promise.all([
      client.get<{ status: string; version: string }>('/health/live'),
      client.get<{ status: string; database: string; redis: string }>('/health/ready'),
    ])
    return {
      status: ready.status,
      database: ready.database,
      redis: ready.redis,
      version: live.version,
      uptime_seconds: 0,
    }
  },

  async getUsers(): Promise<User[]> {
    const { data } = await client.get<{ items: User[] }>('/admin/users')
    return data.items ?? []
  },

  async getSessions(): Promise<SessionRecord[]> {
    const { data } = await client.get<{ sessions: SessionRecord[] }>('/admin/active-sessions')
    return data.sessions ?? []
  },

  async getFeatureFlags(): Promise<FeatureFlagsResponse> {
    const { data } = await client.get<FeatureFlagsResponse>('/feature-flags')
    return data
  },

  async setFeatureFlag(flagName: string, enabled: boolean): Promise<void> {
    await client.put(`/feature-flags/${flagName}`, { enabled })
  },

  async resetFeatureFlag(flagName: string): Promise<void> {
    await client.delete(`/feature-flags/${flagName}`)
  },
}
