import { describe, expect, it } from 'vitest'

import {
	edgeRange,
	junctions,
	nearestJunction,
	orderedStretch,
	stretchLengthM,
	stretchLine,
} from './stretch'

// Two edges: the first bends through a middle point.
const EDGES = [
	{ length_m: 60, last_point: 2 },
	{ length_m: 40, last_point: 3 },
]
const COORDS = [
	[20, 63.8],
	[20.0005, 63.8005],
	[20.001, 63.8],
	[20.002, 63.8],
]

describe('junctions', () => {
	it('are where the route starts and where each edge ends, with the distance so far', () => {
		expect(junctions(EDGES)).toEqual([
			{ point: 0, distanceM: 0 },
			{ point: 2, distanceM: 60 },
			{ point: 3, distanceM: 100 },
		])
	})
})

describe('orderedStretch', () => {
	it('runs in route order whichever end was placed first', () => {
		expect(orderedStretch(3, 1, 4)).toEqual({ from: 1, to: 3 })
	})

	it('covers at least one edge when both ends land on one junction', () => {
		expect(orderedStretch(2, 2, 4)).toEqual({ from: 2, to: 3 })
		expect(orderedStretch(3, 3, 4)).toEqual({ from: 2, to: 3 })
	})
})

describe('edgeRange', () => {
	it('is the edges between the two junctions', () => {
		expect(edgeRange({ from: 1, to: 3 })).toEqual({ fromSeq: 1, toSeq: 2 })
	})
})

describe('nearestJunction', () => {
	const all = junctions(EDGES)

	it('snaps a click to the closest junction', () => {
		expect(nearestJunction(COORDS, all, { lon: 20.0011, lat: 63.8001 })?.index).toBe(1)
	})

	it('takes the pass nearest the other end where a route runs the same street twice', () => {
		const outAndBack = junctions([
			{ length_m: 50, last_point: 1 },
			{ length_m: 50, last_point: 2 },
		])
		const coords = [
			[20, 63.8],
			[20.001, 63.8],
			[20, 63.8],
		]
		const at = { lon: 20, lat: 63.8 }

		expect(nearestJunction(coords, outAndBack, at)?.index).toBe(0)
		expect(nearestJunction(coords, outAndBack, at, 2)?.index).toBe(2)
	})
})

describe('the stretch itself', () => {
	const all = junctions(EDGES)

	it('is the part of the route line between its junctions', () => {
		expect(stretchLine(COORDS, all, { from: 0, to: 1 })).toEqual(COORDS.slice(0, 3))
	})

	it('measures the edges it covers', () => {
		expect(stretchLengthM(all, { from: 1, to: 2 })).toBe(40)
	})
})
