import { describe, expect, it } from 'vitest'

import { chevronsAlong } from './chevrons'

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
