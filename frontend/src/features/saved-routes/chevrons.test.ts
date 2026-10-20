import { describe, expect, it } from 'vitest'

import { chevronsAlong, lineEnds } from './chevrons'

describe('chevronsAlong', () => {
	it('places marks at even steps along the line, pointing the way it runs', () => {
		// About 1.1 km east along the equator, then the same distance north.
		const marks = chevronsAlong(
			[
				[0, 0],
				[0.01, 0],
				[0.01, 0.01],
			],
			500,
		)

		expect(marks.map((m) => Math.round(m.bearingDeg))).toEqual([90, 90, 0, 0])
		expect(marks[0]?.at.lon).toBeCloseTo(0.0045, 4)
		expect(marks[0]?.at.lat).toBeCloseTo(0, 6)
	})

	it('has no marks on a line shorter than one step', () => {
		expect(
			chevronsAlong(
				[
					[0, 0],
					[0.001, 0],
				],
				500,
			),
		).toEqual([])
	})
})

describe('lineEnds', () => {
	it('gives both ends with the way the line runs there', () => {
		const ends = lineEnds([
			[20, 63.8],
			[20, 63.8],
			[20.001, 63.8],
			[20.001, 63.801],
		])

		expect(ends.map((end) => end.at)).toEqual([
			{ lon: 20, lat: 63.8 },
			{ lon: 20.001, lat: 63.801 },
		])
		expect(ends.map((end) => Math.round(end.bearingDeg))).toEqual([90, 0])
	})

	it('has no ends for a line without length', () => {
		expect(lineEnds([[20, 63.8]])).toEqual([])
	})
})
