import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api'

import { useAuthStore } from './store'

const LINA = { email: 'lina@example.se', name: 'Lina' }
const SIGN_IN = { email: LINA.email, password: 'secret123' }

function json(status: number, body?: unknown): Response {
	return new Response(body === undefined ? null : JSON.stringify(body), { status })
}

/**
 * Stubs fetch with canned responses per `METHOD /path`, used in order.
 * A request with no response left fails the test.
 */
function mockApi(responses: Record<string, Response[]>) {
	const calls: { key: string; authorization: string | undefined }[] = []
	vi.stubGlobal('fetch', (url: string, init: RequestInit) => {
		const key = `${init.method} ${url}`
		const headers = init.headers as Record<string, string>
		calls.push({ key, authorization: headers.Authorization })
		const response = responses[key]?.shift()
		if (response === undefined) throw new Error(`Unexpected request: ${key}`)
		return Promise.resolve(response)
	})
	return calls
}

beforeEach(() => {
	setActivePinia(createPinia())
})

afterEach(() => {
	vi.unstubAllGlobals()
})

describe('restore', () => {
	it('stays signed out without a refresh cookie', async () => {
		mockApi({ 'POST /api/auth/refresh': [json(401, { detail: 'Not authenticated' })] })
		const auth = useAuthStore()

		await auth.restore()

		expect(auth.isSignedIn).toBe(false)
	})

	it('picks up the session from the refresh cookie', async () => {
		const calls = mockApi({
			'POST /api/auth/refresh': [json(200, { access_token: 'a1' })],
			'GET /api/auth/me': [json(200, LINA)],
		})
		const auth = useAuthStore()

		await auth.restore()

		expect(auth.user).toEqual(LINA)
		expect(calls.at(-1)).toEqual({ key: 'GET /api/auth/me', authorization: 'Bearer a1' })
	})

	it('only asks the server once', async () => {
		const calls = mockApi({ 'POST /api/auth/refresh': [json(401)] })
		const auth = useAuthStore()

		await Promise.all([auth.restore(), auth.restore()])
		await auth.restore()

		expect(calls).toHaveLength(1)
	})
})

describe('signIn', () => {
	it('loads the user with the new access token', async () => {
		const calls = mockApi({
			'POST /api/auth/login': [json(200, { access_token: 'a1' })],
			'GET /api/auth/me': [json(200, LINA)],
		})
		const auth = useAuthStore()

		await auth.signIn(SIGN_IN)

		expect(auth.user).toEqual(LINA)
		expect(calls.at(-1)?.authorization).toBe('Bearer a1')
	})

	it('passes on a rejected sign-in', async () => {
		mockApi({ 'POST /api/auth/login': [json(401, { detail: 'Invalid email or password' })] })
		const auth = useAuthStore()

		await expect(auth.signIn(SIGN_IN)).rejects.toMatchObject({ status: 401 })
		expect(auth.isSignedIn).toBe(false)
	})
})

describe('authedRequest', () => {
	async function signedIn(more: Record<string, Response[]>) {
		const calls = mockApi({
			'POST /api/auth/login': [json(200, { access_token: 'a1' })],
			'GET /api/auth/me': [json(200, LINA)],
			...more,
		})
		const auth = useAuthStore()
		await auth.signIn(SIGN_IN)
		return { auth, calls }
	}

	it('gets a new access token when the old one expired, and retries', async () => {
		const { auth, calls } = await signedIn({
			'GET /api/logbook/routes': [json(401), json(200, [])],
			'POST /api/auth/refresh': [json(200, { access_token: 'a2' })],
		})

		await expect(auth.authedRequest('/logbook/routes')).resolves.toEqual([])
		expect(calls.at(-1)?.authorization).toBe('Bearer a2')
	})

	it('shares one refresh between requests that expire together', async () => {
		const { auth } = await signedIn({
			'GET /api/logbook/routes': [json(401), json(401), json(200, []), json(200, [])],
			'POST /api/auth/refresh': [json(200, { access_token: 'a2' })],
		})

		await Promise.all([
			auth.authedRequest('/logbook/routes'),
			auth.authedRequest('/logbook/routes'),
		])
	})

	it('signs out when the session has ended', async () => {
		const { auth } = await signedIn({
			'GET /api/logbook/routes': [json(401)],
			'POST /api/auth/refresh': [json(401)],
		})

		await expect(auth.authedRequest('/logbook/routes')).rejects.toBeInstanceOf(ApiError)
		expect(auth.isSignedIn).toBe(false)
	})

	it('passes other errors through without refreshing', async () => {
		const { auth } = await signedIn({ 'GET /api/logbook/routes': [json(500)] })

		await expect(auth.authedRequest('/logbook/routes')).rejects.toMatchObject({ status: 500 })
		expect(auth.isSignedIn).toBe(true)
	})
})

describe('signOut', () => {
	it('forgets the user and has the server revoke the cookie', async () => {
		const calls = mockApi({
			'POST /api/auth/login': [json(200, { access_token: 'a1' })],
			'GET /api/auth/me': [json(200, LINA)],
			'POST /api/auth/logout': [json(204)],
		})
		const auth = useAuthStore()
		await auth.signIn(SIGN_IN)

		await auth.signOut()

		expect(auth.isSignedIn).toBe(false)
		expect(calls.at(-1)?.key).toBe('POST /api/auth/logout')
	})
})
