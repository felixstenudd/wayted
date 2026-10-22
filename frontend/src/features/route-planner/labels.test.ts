import { describe, expect, it } from 'vitest'

import { labelPoints } from './labels'

type Line = [number, number][]

describe('labelPoints', () => {
	it('puts each label where its route is farthest from the others', () => {
		// Two loops from the same start, one north and one south.
		const north: Line = [
			[20.0, 63.8],
			[20.0, 63.81],
			[20.01, 63.81],
			[20.0, 63.8],
		]
		const south: Line = [
			[20.0, 63.8],
			[20.0, 63.79],
			[20.01, 63.79],
			[20.0, 63.8],
		]

		const [a, b] = labelPoints([north, south])

		expect(a).toEqual([20.01, 63.81])
		expect(b).toEqual([20.01, 63.79])
	})

	it('puts a lone route its label halfway along', () => {
		const line: Line = [
			[20.0, 63.8],
			[20.01, 63.8],
			[20.02, 63.8],
		]

		expect(labelPoints([line])).toEqual([[20.01, 63.8]])
	})
})
