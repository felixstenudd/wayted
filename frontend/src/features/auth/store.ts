import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
	ApiError,
	isUnauthorized,
	request,
	requestFile,
	type DownloadedFile,
	type RequestOptions,
} from '@/shared/api'

import * as api from './api'
import type { CreateAccountValues, SignInValues, User } from './types'

export const useAuthStore = defineStore('auth', () => {
	const user = ref<User | null>(null)
	const isSignedIn = computed(() => user.value !== null)

	// Kept in memory only, and not returned from the store. A reload loses it
	// and gets a new one from the refresh cookie.
	let accessToken: string | null = null
	let pendingRefresh: Promise<string | null> | null = null
	let restoring: Promise<void> | null = null

	/**
	 * Trades the refresh cookie for a new access token, or null when there is
	 * no session. Calls made while one is in flight share it.
	 */
	function refresh(): Promise<string | null> {
		pendingRefresh ??= oneTabAtATime(async () => {
			try {
				accessToken = await api.refresh()
			} catch (error) {
				if (!isUnauthorized(error)) throw error
				accessToken = null
				user.value = null
			}
			return accessToken
		}).finally(() => {
			pendingRefresh = null
		})
		return pendingRefresh
	}

	/**
	 * Makes a call that needs a signed-in user. Access tokens are short-lived,
	 * so on a 401 it gets a new one and tries once more.
	 */
	async function withToken<T>(call: (token: string) => Promise<T>): Promise<T> {
		if (accessToken !== null) {
			try {
				return await call(accessToken)
			} catch (error) {
				if (!isUnauthorized(error)) throw error
			}
		}
		const token = await refresh()
		if (token === null) throw new ApiError(401, 'Not signed in')
		return call(token)
	}

	/** Like `request`, for endpoints that need a signed-in user. */
	function authedRequest<T>(
		path: string,
		options: Omit<RequestOptions, 'token'> = {},
	): Promise<T> {
		return withToken((token) => request<T>(path, { ...options, token }))
	}

	/** Like `requestFile`, for endpoints that need a signed-in user. */
	function authedFile(path: string): Promise<DownloadedFile> {
		return withToken((token) => requestFile(path, { token }))
	}

	/** Picks up an existing session on page load. Runs once; later calls wait for the first. */
	function restore(): Promise<void> {
		restoring ??= (async () => {
			try {
				user.value = await authedRequest<User>('/auth/me')
			} catch (error) {
				// Not being signed in is normal. Anything else is worth a look.
				if (!isUnauthorized(error)) console.error('Could not restore the session', error)
			}
		})()
		return restoring
	}

	async function signIn(values: SignInValues): Promise<void> {
		accessToken = await api.login(values)
		user.value = await authedRequest<User>('/auth/me')
	}

	async function createAccount(values: CreateAccountValues): Promise<void> {
		accessToken = await api.register(values)
		user.value = await authedRequest<User>('/auth/me')
	}

	/** Forgets the session here first, so the UI signs out even if the server is unreachable. */
	async function signOut(): Promise<void> {
		accessToken = null
		user.value = null
		await api.logout()
	}

	return {
		user,
		isSignedIn,
		restore,
		signIn,
		createAccount,
		signOut,
		authedRequest,
		authedFile,
	}
})

/**
 * The server swaps the refresh cookie on every refresh, and treats a second use
 * of an old one as theft by ending the session. All tabs share the cookie, so
 * two tabs refreshing at the same moment (say, when the browser reopens them)
 * would end the session. A Web Lock makes tabs take turns, so each one sends
 * the newest cookie.
 */
function oneTabAtATime<T>(task: () => Promise<T>): Promise<T> {
	// Web Locks are missing on plain-http pages other than localhost, and in tests.
	if (!('locks' in navigator)) return task()
	return navigator.locks.request('auth-refresh', task)
}
