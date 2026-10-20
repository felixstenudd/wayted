import { describe, expect, it } from 'vitest'

import { silhouette } from './silhouette'

describe('silhouette', () => {
	it('fits the line into the box, centred, with north up', () => {
		// 0.002° of longitude at 60° north is as long as 0.001° of latitude: a square.
		const shape = silhouette(
			[
				[18, 60],
				[18.002, 60],
				[18.002, 60.001],
			],
			{ width: 44, height: 32, padding: 4 },
		)

		expect(shape?.path).toBe('M10 28L34 28L34 4')
		expect(shape?.start).toEqual({ x: 10, y: 28 })
	})

	it('keeps the shape of a long route instead of stretching it', () => {
		const shape = silhouette(
			[
				[18, 0],
				[18.01, 0],
			],
			{ width: 44, height: 32, padding: 4 },
		)

		expect(shape?.path).toBe('M4 16L40 16')
	})

	it('puts a route that never moves in the middle', () => {
		const shape = silhouette(
			[
				[18, 60],
				[18, 60],
			],
			{ width: 44, height: 32, padding: 4 },
		)

		expect(shape?.start).toEqual({ x: 22, y: 16 })
	})

	it('has nothing to draw without coordinates', () => {
		expect(silhouette([], { width: 44, height: 32, padding: 4 })).toBeNull()
	})
})
