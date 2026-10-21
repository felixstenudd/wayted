import { describe, expect, it } from 'vitest'

import { needsCoverageNote, profileRows, scoreWord } from './profile'

describe('scoreWord', () => {
	it('puts a share of the route into one of five words', () => {
		expect([0, 0.04, 0.1, 0.3, 0.6, 0.75, 1].map(scoreWord)).toEqual([
			'none',
			'none',
			'aLittle',
			'some',
			'aLot',
			'mostly',
			'mostly',
		])
	})
})

describe('profileRows', () => {
	const scores = {
		water: { mean: 0.2, coverage: 1 },
		prepared: { mean: 0.9, coverage: 0.4 },
		green: { mean: 0.6, coverage: 1 },
		nature: { mean: 0.4, coverage: 1 },
	}
	const order = ['green', 'nature', 'water', 'prepared']

	it('lists what the route was planned for first, each part in attribute order', () => {
		const rows = profileRows(scores, { water: 0.5, green: 1 }, order)

		expect(rows.map((r) => [r.key, r.weight])).toEqual([
			['green', 1],
			['water', 0.5],
			['nature', 0],
			['prepared', 0],
		])
	})

	it('puts attributes it does not know the order of last', () => {
		const rows = profileRows({ ...scores, hills: { mean: 0.1, coverage: 1 } }, {}, order)

		expect(rows.at(-1)?.key).toBe('hills')
	})
})

describe('needsCoverageNote', () => {
	it('notes coverage when under nine tenths of the route is known', () => {
		expect(needsCoverageNote(0.89)).toBe(true)
		expect(needsCoverageNote(0.9)).toBe(false)
	})
})
