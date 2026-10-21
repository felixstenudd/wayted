import { describe, expect, it } from 'vitest'

import { optionLetter, routeFit, standOut } from './options'

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

describe('standOut', () => {
	const scored = (means: Record<string, number>) =>
		Object.fromEntries(Object.entries(means).map(([key, mean]) => [key, { mean, coverage: 1 }]))
	const KEYS = ['green', 'nature', 'water']

	it('is the attribute an option has in other words than every other option', () => {
		const options = [
			scored({ green: 0.1, water: 0 }),
			scored({ green: 0.1, water: 0.6 }),
			scored({ green: 0.4, water: 0 }),
		]

		expect(standOut(options, {}, KEYS)).toEqual([null, 'water', 'green'])
	})

	it('is an attribute the user weighted before a bigger difference in another', () => {
		const options = [scored({ green: 0.3, water: 0 }), scored({ green: 0, water: 0.9 })]

		expect(standOut(options, { green: 0.5 }, KEYS)).toEqual(['green', 'green'])
	})

	it('leaves out attributes it has no words for, or that an option was not scored for', () => {
		const options = [scored({ green: 0, quiet: 0.9 }), scored({ quiet: 0, green: 0.6 })]

		expect(standOut([options[0]!, options[1]!, scored({ quiet: 0.5 })], {}, KEYS)).toEqual([
			null,
			null,
			null,
		])
		expect(standOut(options, {}, KEYS)).toEqual(['green', 'green'])
	})
})
