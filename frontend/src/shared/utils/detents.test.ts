import { describe, expect, it } from 'vitest'

import { nearestDetent, nextDetent, roundToHundredth, valueAtX } from './detents'

const DETENTS = [-1, -0.5, 0, 0.5, 1]

describe('nearestDetent', () => {
	it.each([
		[0.2, 0],
		[0.3, 0.5],
		[-0.74, -0.5],
		[-0.76, -1],
		[1, 1],
	])('takes %d to %d', (value, detent) => {
		expect(nearestDetent(value, DETENTS)).toBe(detent)
	})
})

describe('nextDetent', () => {
	it('steps to the next detent in a direction', () => {
		expect(nextDetent(0, DETENTS, 1)).toBe(0.5)
		expect(nextDetent(0, DETENTS, -1)).toBe(-0.5)
	})

	it('steps from between detents to the next one beyond', () => {
		expect(nextDetent(0.37, DETENTS, 1)).toBe(0.5)
		expect(nextDetent(0.37, DETENTS, -1)).toBe(0)
	})

	it('stays at the ends', () => {
		expect(nextDetent(1, DETENTS, 1)).toBe(1)
		expect(nextDetent(-1, DETENTS, -1)).toBe(-1)
	})
})

describe('valueAtX', () => {
	it('maps a track from -1 at its left edge to 1 at its right edge', () => {
		expect(valueAtX(100, 100, 200)).toBe(-1)
		expect(valueAtX(200, 100, 200)).toBe(0)
		expect(valueAtX(250, 100, 200)).toBe(0.5)
		expect(valueAtX(300, 100, 200)).toBe(1)
	})

	it('stays within -1 and 1 outside the track', () => {
		expect(valueAtX(0, 100, 200)).toBe(-1)
		expect(valueAtX(900, 100, 200)).toBe(1)
	})
})

describe('roundToHundredth', () => {
	it('rounds to 0.01 without float noise', () => {
		expect(roundToHundredth(0.374)).toBe(0.37)
		expect(roundToHundredth(0.1 + 0.2)).toBe(0.3)
		expect(roundToHundredth(-0.005)).toBe(-0)
	})
})
