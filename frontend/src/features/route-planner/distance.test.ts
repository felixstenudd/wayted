import { describe, expect, it } from 'vitest'

import { formatKm, parseDistanceKm, steppedKm } from './distance'

describe('parseDistanceKm', () => {
	it.each([
		['10', 10],
		[' 10.5 ', 10.5],
		['10,5', 10.5],
		['21.1 km', 21.1],
		['42KM', 42],
	])('reads %j as %d km', (text, km) => {
		expect(parseDistanceKm(text)).toBe(km)
	})

	it.each(['', 'ten', '10..5', '-5', '0', 'km'])('rejects %j', (text) => {
		expect(parseDistanceKm(text)).toBeNull()
	})
})

describe('formatKm', () => {
	it('drops a zero decimal and keeps one decimal otherwise', () => {
		expect(formatKm(10)).toBe('10')
		expect(formatKm(10.5)).toBe('10.5')
	})
})

describe('steppedKm', () => {
	it('moves to the next whole step', () => {
		expect(steppedKm(10, 1, 1)).toBe(11)
		expect(steppedKm(10, 1, -1)).toBe(9)
		expect(steppedKm(25, 5, 1)).toBe(30)
	})

	it('lands on the step grid from between steps', () => {
		expect(steppedKm(10.5, 1, 1)).toBe(11)
		expect(steppedKm(10.5, 1, -1)).toBe(10)
		expect(steppedKm(27, 5, -1)).toBe(25)
	})
})
