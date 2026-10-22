import { describe, expect, it } from 'vitest'

import { planOf } from './planAgain'

describe('planOf', () => {
	it('starts and finishes where the saved line does', () => {
		const plan = planOf({
			activity: 'running',
			shape: 'point_to_point',
			target_distance_m: null,
			preferences: { green: 1 },
			waypoints: [{ lon: 20.28, lat: 63.82, at: 'any', after_m: null }],
			geometry: {
				type: 'LineString',
				coordinates: [
					[20.26, 63.82],
					[20.27, 63.825],
					[20.3, 63.83],
				],
			},
		})

		expect(plan).toEqual({
			activity: 'running',
			shape: 'point_to_point',
			start: { lon: 20.26, lat: 63.82 },
			finish: { lon: 20.3, lat: 63.83 },
			targetDistanceM: null,
			preferences: { green: 1 },
			waypoints: [{ lon: 20.28, lat: 63.82, at: 'any', after_m: null }],
		})
	})

	it('has no plan for a route without a line', () => {
		expect(
			planOf({
				activity: 'running',
				shape: 'loop',
				target_distance_m: 5_000,
				preferences: {},
				waypoints: [],
				geometry: { type: 'LineString', coordinates: [] },
			}),
		).toBeNull()
	})
})
