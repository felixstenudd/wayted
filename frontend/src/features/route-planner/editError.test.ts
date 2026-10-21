import { describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api'

import { editError } from './editError'

describe('editError', () => {
	it.each([
		['drop_off_road', 'dropOffRoad'],
		['unreachable', 'unreachable'],
		['route_changed', 'routeChanged'],
	])('names an edit with no way because of %s "%s"', (reason, key) => {
		expect(editError(new ApiError(422, reason))).toBe(key)
	})

	it.each([
		[401, 'signedOut'],
		[503, 'tooSlow'],
		[422, 'unexpected'],
	])('names a %i answer "%s"', (status, key) => {
		expect(editError(new ApiError(status))).toBe(key)
	})

	it('names a failed connection "unexpected"', () => {
		expect(editError(new TypeError('Failed to fetch'))).toBe('unexpected')
	})
})
