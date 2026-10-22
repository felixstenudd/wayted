import { describe, expect, it } from 'vitest'

import { suggestRouteName } from './naming'

describe('suggestRouteName', () => {
	it('names a loop by the distance asked for', () => {
		expect(suggestRouteName({ shape: 'loop', targetM: 8_000, lengthM: 8_312 })).toEqual({
			key: 'route.name.loop',
			values: { km: '8' },
		})
	})

	it('names a way to a finish by its length, which nobody asked for', () => {
		expect(
			suggestRouteName({ shape: 'point_to_point', targetM: null, lengthM: 5_230 }),
		).toEqual({ key: 'route.name.route', values: { km: '5.2' } })
	})

	it('names a way to a finish with a target by the target', () => {
		expect(
			suggestRouteName({ shape: 'point_to_point', targetM: 10_500, lengthM: 10_100 }),
		).toEqual({ key: 'route.name.route', values: { km: '10.5' } })
	})
})
