import { describe, expect, it } from 'vitest'

import { soonOrder, throughPointNumbers, skippedPoints } from './throughPoints'

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

describe('soonOrder', () => {
	it('counts the points that go as soon as possible in the order they were added', () => {
		const points = [
			{ id: 1, placement: { at: 'any' } },
			{ id: 2, placement: { at: 'asap' } },
			{ id: 3, placement: { at: 'after', afterKm: 3 } },
			{ id: 4, placement: { at: 'asap' } },
		] as const

		expect(soonOrder(points)).toEqual(
			new Map([
				[2, 1],
				[4, 2],
			]),
		)
	})
})

describe('skippedPoints', () => {
	// A street in Umeå running east, and one about 110 m north of it.
	const south: [number, number][] = [
		[20.25, 63.82],
		[20.27, 63.82],
	]
	const north: [number, number][] = [
		[20.25, 63.821],
		[20.27, 63.821],
	]

	it('are the points an edit took the route away from', () => {
		const onSouth = { lon: 20.26, lat: 63.82 }
		const onNorth = { lon: 20.26, lat: 63.821 }

		expect(skippedPoints([onSouth, onNorth], south, north)).toEqual([true, false])
	})

	it('leave out a point the planned route already passed at a distance', () => {
		// About 40 m off the street, which the planner took as the nearest road.
		const beside = { lon: 20.26, lat: 63.8196 }

		expect(skippedPoints([beside], south, south)).toEqual([false])
	})
})
