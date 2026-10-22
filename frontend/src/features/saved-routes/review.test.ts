import { describe, expect, it } from 'vitest'

import { answeredOnly, changeKind, sliderPercent } from './review'

describe('changeKind', () => {
	it('says which way a weight moved, or that it was already at the end', () => {
		expect(changeKind({ attribute: 'green', before: 0.1, after: 0.2 })).toBe('raised')
		expect(changeKind({ attribute: 'green', before: 0, after: -0.1 })).toBe('lowered')
		expect(changeKind({ attribute: 'green', before: 1, after: 1 })).toBe('atEnd')
	})
})

describe('answeredOnly', () => {
	it('keeps the rows that were answered', () => {
		expect(answeredOnly({ green: 1, water: null, nature: 0 })).toEqual({ green: 1, nature: 0 })
	})
})

describe('sliderPercent', () => {
	it('places a weight from avoid at the left to prefer at the right', () => {
		expect([-1, -0.5, 0, 0.1, 1].map(sliderPercent)).toEqual([0, 25, 50, 55, 100])
	})
})
