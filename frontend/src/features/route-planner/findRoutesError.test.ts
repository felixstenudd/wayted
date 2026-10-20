import { describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api'

import { findRoutesError } from './findRoutesError'

describe('findRoutesError', () => {
	it.each([
		[501, 'notAvailable'],
		[422, 'notAccepted'],
		[401, 'signedOut'],
		[500, 'unexpected'],
	])('names a %i answer "%s"', (status, key) => {
		expect(findRoutesError(new ApiError(status))).toBe(key)
	})

	it('names a failed connection "unexpected"', () => {
		expect(findRoutesError(new TypeError('Failed to fetch'))).toBe('unexpected')
	})

	it('names no error null', () => {
		expect(findRoutesError(null)).toBeNull()
	})
})
