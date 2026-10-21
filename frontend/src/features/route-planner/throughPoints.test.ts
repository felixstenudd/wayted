import { describe, expect, it } from 'vitest'

import { throughPointNumbers } from './throughPoints'

describe('throughPointNumbers', () => {
	it('numbers points by where the route passes them', () => {
		// The second point added is passed first.
		expect(throughPointNumbers([1, 2, 0], 3)).toEqual([3, 1, 2])
	})

	it('leaves points unnumbered until a route says their order', () => {
		expect(throughPointNumbers(null, 2)).toEqual([undefined, undefined])
	})

	it('leaves a point the order does not mention unnumbered', () => {
		expect(throughPointNumbers([0], 2)).toEqual([1, undefined])
	})
})
