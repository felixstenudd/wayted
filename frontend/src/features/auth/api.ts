import { request } from '@/shared/api'

import type { CreateAccountValues, SignInValues } from './types'

// These endpoints answer with an access token and set the refresh token as an
// httpOnly cookie. The browser stores and sends that cookie by itself; this
// code never sees it.

interface AccessTokenResponse {
	access_token: string
}

async function postForAccessToken(path: string, body?: unknown): Promise<string> {
	const response = await request<AccessTokenResponse>(path, { method: 'POST', body })
	return response.access_token
}

export function login(values: SignInValues): Promise<string> {
	return postForAccessToken('/auth/login', values)
}

export function register(values: CreateAccountValues): Promise<string> {
	return postForAccessToken('/auth/register', values)
}

export function refresh(): Promise<string> {
	return postForAccessToken('/auth/refresh')
}

export function logout(): Promise<void> {
	return request('/auth/logout', { method: 'POST' })
}
