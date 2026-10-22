import { describe, expect, it } from 'vitest'

import { climbText, formatClimbM, isFlat, roundClimbM } from './climb'

describe('roundClimbM', () => {
	it('rounds to 5 m under 100 m and to 10 m from there', () => {
		expect([2, 3, 12, 97, 99.9, 100, 104, 106, 1234].map(roundClimbM)).toEqual([
			0, 5, 10, 95, 100, 100, 100, 110, 1230,
		])
	})
})

describe('isFlat', () => {
	it('is flat only while both the climb and the drop are under 10 m', () => {
		expect(isFlat(9.9, 4)).toBe(true)
		expect(isFlat(10, 0)).toBe(false)
		expect(isFlat(0, 40)).toBe(false)
	})
})

describe('formatClimbM', () => {
	it('writes the rounded metres for the locale', () => {
		expect(formatClimbM(1234, 'en')).toBe('1,230')
		expect(formatClimbM(47, 'en')).toBe('45')
	})
})

describe('climbText', () => {
	const t = (key: string, named: Record<string, string>) => `${key} ${JSON.stringify(named)}`

	it('says both ways in rounded metres', () => {
		expect(climbText(122, 47, t, 'en')).toBe('route.climb.upDown {"up":"120","down":"45"}')
	})

	it('says flat when neither way reaches 10 m', () => {
		expect(climbText(4, 6, t, 'en')).toBe('route.climb.flat {}')
	})

	it('says nothing while the heights are not known', () => {
		expect(climbText(null, 3, t, 'en')).toBeNull()
		expect(climbText(undefined, undefined, t, 'en')).toBeNull()
	})
})
