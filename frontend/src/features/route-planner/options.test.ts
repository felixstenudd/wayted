import { describe, expect, it } from 'vitest'

import { optionLetter, routeFit } from './options'

describe('optionLetter', () => {
	it('names options A, B, C, so they are not taken for through point numbers', () => {
		expect([0, 1, 2].map(optionLetter)).toEqual(['A', 'B', 'C'])
	})
})

describe('routeFit', () => {
	it('is close within the tolerance the planner keeps to', () => {
		expect(routeFit(8_300, 8_000)).toEqual({ kind: 'close' })
		expect(routeFit(7_500, 8_000)).toEqual({ kind: 'close' })
	})

	it('says how much longer or shorter a route is beyond it', () => {
		expect(routeFit(8_600, 8_000)).toEqual({ kind: 'long', km: 0.6 })
		expect(routeFit(6_900, 8_000)).toEqual({ kind: 'short', km: 1.1 })
	})

	it('has nothing to say without a target', () => {
		expect(routeFit(8_600, null)).toBeNull()
		expect(routeFit(8_600, undefined)).toBeNull()
	})
})
