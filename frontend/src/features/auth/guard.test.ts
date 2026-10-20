import { describe, expect, it } from 'vitest'
import type { RouteLocationNormalized, RouteMeta } from 'vue-router'

import { authRedirect, safeRedirect } from './guard'

const ROUTES = { signIn: 'sign-in', home: 'planner' }

function route(fullPath: string, meta: RouteMeta = {}): RouteLocationNormalized {
	return { fullPath, meta } as RouteLocationNormalized
}

describe('authRedirect', () => {
	it('sends someone signed out to sign in, remembering where they were going', () => {
		const to = route('/plan?x=1', { access: 'signed-in' })

		expect(authRedirect(to, false, ROUTES)).toEqual({
			name: 'sign-in',
			query: { redirect: '/plan?x=1' },
		})
	})

	it('sends someone signed in from a signed-out page to the home page', () => {
		expect(authRedirect(route('/', { access: 'signed-out' }), true, ROUTES)).toEqual({
			name: 'planner',
		})
	})

	it('lets everyone else through', () => {
		expect(authRedirect(route('/plan', { access: 'signed-in' }), true, ROUTES)).toBeUndefined()
		expect(authRedirect(route('/', { access: 'signed-out' }), false, ROUTES)).toBeUndefined()
		expect(authRedirect(route('/about'), false, ROUTES)).toBeUndefined()
		expect(authRedirect(route('/about'), true, ROUTES)).toBeUndefined()
	})
})

describe('safeRedirect', () => {
	it('keeps a path on this site', () => {
		expect(safeRedirect('/plan?x=1')).toBe('/plan?x=1')
	})

	it.each([undefined, null, '', 'plan', '//evil.example', 'https://evil.example', ['/plan']])(
		'drops %j',
		(redirect) => {
			expect(safeRedirect(redirect)).toBeUndefined()
		},
	)
})
