import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePlannerStore } from './store'

const UMEA = { lon: 20.26, lat: 63.82 }
const TAVLEBORG = { lon: 20.3, lat: 63.83 }

beforeEach(() => {
	setActivePinia(createPinia())
})

describe('target distance', () => {
	it('starts at the running default', () => {
		expect(usePlannerStore().targetDistanceKm).toBe(5)
	})

	it('is kept in the activity range and to one decimal', () => {
		const planner = usePlannerStore()

		planner.setTargetDistanceKm(0.2)
		expect(planner.targetDistanceKm).toBe(1)
		planner.setTargetDistanceKm(80)
		expect(planner.targetDistanceKm).toBe(50)
		planner.setTargetDistanceKm(21.0975)
		expect(planner.targetDistanceKm).toBe(21.1)
	})

	it('is kept when switching activity if it fits the new range', () => {
		const planner = usePlannerStore()
		planner.setTargetDistanceKm(30)

		planner.setActivity('cycling')

		expect(planner.targetDistanceKm).toBe(30)
	})

	it('goes to the new default when it does not fit the new range', () => {
		const planner = usePlannerStore()
		planner.setActivity('cycling')
		planner.setTargetDistanceKm(120)

		planner.setActivity('running')

		expect(planner.targetDistanceKm).toBe(5)
	})
})

describe('preference weights', () => {
	it('are "don\'t mind" until set', () => {
		const planner = usePlannerStore()

		expect(planner.weightOf('green')).toBe(0)
		expect(planner.setWeightCount).toBe(0)
	})

	it('are kept between -1 and 1 at 0.01 steps', () => {
		const planner = usePlannerStore()

		planner.setWeight('green', 0.374)
		planner.setWeight('nature', -3)
		planner.setWeight('water', 1.5)

		expect(planner.preferenceWeights).toEqual({ green: 0.37, nature: -1, water: 1 })
	})

	it('drop a weight set back to "don\'t mind"', () => {
		const planner = usePlannerStore()
		planner.setWeight('green', 0.5)

		planner.setWeight('green', 0.004)

		expect(planner.preferenceWeights).toEqual({})
	})

	it('reset one or all', () => {
		const planner = usePlannerStore()
		planner.setWeight('green', 0.5)
		planner.setWeight('gravel', -1)

		planner.resetWeight('green')
		expect(planner.preferenceWeights).toEqual({ gravel: -1 })
		planner.resetWeights()
		expect(planner.setWeightCount).toBe(0)
	})
})

describe('route request', () => {
	it('is missing the start until one is placed', () => {
		const planner = usePlannerStore()

		expect(planner.missingPoint).toBe('start')
		expect(planner.routeRequest).toBeNull()
	})

	it('is a loop from the start with the set weights', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.setTargetDistanceKm(10.5)
		planner.setWeight('nature', 0.5)

		expect(planner.routeRequest).toEqual({
			activity: 'running',
			shape: 'loop',
			start: UMEA,
			target_distance_m: 10_500,
			preferences: { nature: 0.5 },
		})
	})

	it('needs a finish from point to point', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.shape = 'point_to_point'

		expect(planner.missingPoint).toBe('finish')
		planner.finish = TAVLEBORG
		expect(planner.routeRequest).toMatchObject({ shape: 'point_to_point', finish: TAVLEBORG })
	})

	it('leaves the distance out from point to point when any length will do', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.shape = 'point_to_point'
		planner.finish = TAVLEBORG

		planner.hasTargetDistance = false

		expect(planner.routeRequest).not.toHaveProperty('target_distance_m')
	})

	it('always gives a loop a distance', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.hasTargetDistance = false

		expect(planner.usesTargetDistance).toBe(true)
		expect(planner.routeRequest).toMatchObject({ shape: 'loop', target_distance_m: 5_000 })
	})

	it('keeps the finish for later but leaves it out of a loop', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.finish = TAVLEBORG

		planner.shape = 'loop'

		expect(planner.finish).toEqual(TAVLEBORG)
		expect(planner.routeRequest).not.toHaveProperty('finish')
	})
})

describe('placeNextPoint', () => {
	it('places the start first', () => {
		const planner = usePlannerStore()

		expect(planner.placeNextPoint(UMEA)).toBe(true)
		expect(planner.start).toEqual(UMEA)
	})

	it('places the finish next, from point to point', () => {
		const planner = usePlannerStore()
		planner.shape = 'point_to_point'
		planner.placeNextPoint(UMEA)

		expect(planner.placeNextPoint(TAVLEBORG)).toBe(true)
		expect(planner.finish).toEqual(TAVLEBORG)
	})

	it('leaves placed points alone once nothing is missing', () => {
		const planner = usePlannerStore()
		planner.placeNextPoint(UMEA)

		expect(planner.placeNextPoint(TAVLEBORG)).toBe(false)
		expect(planner.start).toEqual(UMEA)
		expect(planner.finish).toBeNull()
	})
})

describe('findRoutes', () => {
	it('does nothing until the points are placed', () => {
		const planner = usePlannerStore()

		expect(planner.findRoutes()).toBe(false)
		expect(planner.search).toBeNull()
	})

	it('searches for the current request, anew on every press', () => {
		const planner = usePlannerStore()
		planner.start = UMEA

		planner.findRoutes()
		const first = planner.search
		planner.findRoutes()

		expect(first?.request).toEqual(planner.routeRequest)
		expect(planner.search?.request).toEqual(planner.routeRequest)
		expect(planner.search?.id).not.toBe(first?.id)
	})

	it('drops the search once the request changes', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()

		planner.setWeight('green', 1)

		expect(planner.search).toBeNull()
	})
})
