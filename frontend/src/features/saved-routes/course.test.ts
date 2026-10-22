import { describe, expect, it } from 'vitest'

import { endsAtStart } from './course'

describe('endsAtStart', () => {
	it('is true when the finish is within 30 m of the start', () => {
		const loop = [
			[18.0, 59.3],
			[18.01, 59.31],
			[18.0002, 59.3001],
		]
		expect(endsAtStart(loop)).toBe(true)
	})

	it('is false when the finish is farther away', () => {
		expect(
			endsAtStart([
				[18.0, 59.3],
				[18.001, 59.3],
			]),
		).toBe(false)
	})

	it('is false for an empty line', () => {
		expect(endsAtStart([])).toBe(false)
	})
})
