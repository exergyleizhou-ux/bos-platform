/**
 * BOS Pipeline v9.0 -Auth API
 *
 * API functions for authentication endpoints.
 */

import axios from "axios";
import client from "@/api/client";
import type { User, LoginRequest, TokenPair } from "@/types/auth";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const authApi = {
 /**
 * Login - uses plain axios (no interceptor) because we don't have a token yet.
 */
 async login(credentials: LoginRequest): Promise<TokenPair> {
 const { data } = await axios.post<TokenPair>(
 `${BASE}/auth/login`,
 credentials,
 { timeout: 15_000 },
 );
 return data;
 },

 /**
 * Get current user profile.
 */
 async me(): Promise<User> {
 const { data } = await client.get<User>("/auth/me");
 return data;
 },

 /**
 * Refresh token.
 */
 async refresh(refreshToken: string): Promise<TokenPair> {
 const { data } = await axios.post<TokenPair>(`${BASE}/auth/refresh`, {
 refresh_token: refreshToken,
 });
 return data;
 },

 /**
 * Change password.
 */
 async changePassword(payload: {
 current_password: string;
 new_password: string;
 }): Promise<void> {
 await client.post("/auth/change-password", payload);
 },
};
