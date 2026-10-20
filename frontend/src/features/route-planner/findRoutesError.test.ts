import { describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api'

import { findRoutesError } from './findRoutesError'

describe('findRoutesError', () => {
	it.each([
		[422, 'notAccepted'],
		[503, 'tooSlow'],
		[401, 'signedOut'],
		[500, 'unexpected'],
	])('names a %i answer "%s"', (status, key) => {
		expect(findRoutesError(new ApiError(status))).toBe(key)
	})

	it.each([
		['start_off_road', 'startOffRoad'],
		['finish_off_road', 'finishOffRoad'],
		['unreachable', 'unreachable'],
		['no_loop', 'noLoop'],
	])('names a 422 with no route because of %s "%s"', (reason, key) => {
		expect(findRoutesError(new ApiError(422, reason))).toBe(key)
	})

	it('names a 422 with any other detail "notAccepted"', () => {
		expect(findRoutesError(new ApiError(422, 'toString'))).toBe('notAccepted')
	})

	it('names a failed connection "unexpected"', () => {
		expect(findRoutesError(new TypeError('Failed to fetch'))).toBe('unexpected')
	})

	it('names no error null', () => {
		expect(findRoutesError(null)).toBeNull()
	})
})
