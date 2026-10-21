import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePlannerStore } from './store'
import type { Route } from './types'

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

	it('reset one at a time', () => {
		const planner = usePlannerStore()
		planner.setWeight('green', 0.5)
		planner.setWeight('prepared', -1)

		planner.resetWeight('green')
		expect(planner.preferenceWeights).toEqual({ prepared: -1 })
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
			waypoints: [],
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
})

describe('through points', () => {
	const NYDALA = { lon: 20.31, lat: 63.82 }

	it('are added by map clicks once the start is placed', () => {
		const planner = usePlannerStore()
		planner.placeNextPoint(UMEA)

		expect(planner.placeNextPoint(TAVLEBORG)).toBe(true)
		planner.placeNextPoint(NYDALA)

		expect(planner.throughPoints.map((point) => point.lonLat)).toEqual([TAVLEBORG, NYDALA])
		expect(planner.start).toEqual(UMEA)
	})

	it('are not added by map clicks while a route is shown', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()

		expect(planner.placeNextPoint(TAVLEBORG)).toBe(false)
		expect(planner.throughPoints).toEqual([])
	})

	it('go to the planner wherever they fit, in the order added', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.addThroughPoint(TAVLEBORG)
		planner.addThroughPoint(NYDALA)

		expect(planner.routeRequest?.waypoints).toEqual([
			{ ...TAVLEBORG, at: 'any' },
			{ ...NYDALA, at: 'any' },
		])
	})

	it('can be moved and removed one by one or all at once', () => {
		const planner = usePlannerStore()
		const first = planner.addThroughPoint(TAVLEBORG)
		const second = planner.addThroughPoint(NYDALA)

		planner.moveThroughPoint(first, UMEA)
		planner.removeThroughPoint(second)
		expect(planner.throughPoints.map((point) => point.lonLat)).toEqual([UMEA])

		planner.clearThroughPoints()
		expect(planner.throughPoints).toEqual([])
	})

	it('can go first, or after a distance, as the planner takes them', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		const first = planner.addThroughPoint(TAVLEBORG)
		const later = planner.addThroughPoint(NYDALA)

		planner.setThroughPointPlacement(first, { at: 'asap' })
		planner.setThroughPointPlacement(later, { at: 'after', afterKm: 2.5 })

		expect(planner.routeRequest?.waypoints).toEqual([
			{ ...TAVLEBORG, at: 'asap' },
			{ ...NYDALA, at: 'after', after_m: 2_500 },
		])
	})

	it('stop being edited once removed', () => {
		const planner = usePlannerStore()
		const point = planner.addThroughPoint(TAVLEBORG)
		planner.editThroughPoint(point)
		expect(planner.editingThroughPointId).toBe(point)

		planner.removeThroughPoint(point)

		expect(planner.editingThroughPointId).toBeNull()
	})

	it('make a found route stale when they change', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()

		planner.addThroughPoint(TAVLEBORG)

		expect(planner.search).toBeNull()
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

	it('keeps the search when the request is set again to what it was', () => {
		const planner = usePlannerStore()
		planner.receiveDefaults({ green: 0.5 })
		planner.start = UMEA
		planner.findRoutes()

		planner.receiveDefaults({ green: 0.5 })

		expect(planner.search).not.toBeNull()
	})

	it('drops the search once the request changes', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()

		planner.setWeight('green', 1)

		expect(planner.search).toBeNull()
	})
})

describe('route options', () => {
	it('start at the best, and step to others until the next search', () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()
		expect(planner.selectedOption).toBe(0)

		planner.selectOption(2)
		expect(planner.selectedOption).toBe(2)

		planner.findRoutes()
		expect(planner.selectedOption).toBe(0)
	})
})

describe('route edits', () => {
	const route = (lengthM: number): Route => ({
		type: 'Feature',
		geometry: { type: 'LineString', coordinates: [] },
		properties: {
			length_m: lengthM,
			scores: {},
			reused_m: 0,
			warnings: [],
			edges: [],
			waypoint_order: [],
		},
	})
	const searched = () => {
		const planner = usePlannerStore()
		planner.start = UMEA
		planner.findRoutes()
		return planner
	}

	it('stack up on the option they were made to, with the handles of each', () => {
		const planner = searched()
		planner.selectOption(1)

		planner.applyEdit(route(8_000), route(8_300), [TAVLEBORG])

		expect(planner.edit?.option).toBe(1)
		expect(planner.edit?.steps.map((step) => step.route.properties.length_m)).toEqual([
			8_000, 8_300,
		])
		expect(planner.editedRoute?.properties.length_m).toBe(8_300)
		expect(planner.editHandles).toEqual([TAVLEBORG])
	})

	it('step back one at a time, until there is nothing left to undo', () => {
		const planner = searched()
		planner.applyEdit(route(8_000), route(8_300), [TAVLEBORG])
		planner.applyEdit(route(8_000), route(8_500), [TAVLEBORG, UMEA])

		planner.undoEdit()
		expect(planner.editedRoute?.properties.length_m).toBe(8_300)
		expect(planner.editHandles).toEqual([TAVLEBORG])

		planner.undoEdit()
		expect(planner.edit).toBeNull()
	})

	it('ask before another option is shown, and lose the edits once it is', () => {
		const planner = searched()
		planner.applyEdit(route(8_000), route(8_300), [TAVLEBORG])

		planner.selectOption(2)
		expect(planner.selectedOption).toBe(0)
		expect(planner.pendingOption).toBe(2)

		planner.confirmOption()
		expect(planner.selectedOption).toBe(2)
		expect(planner.edit).toBeNull()
		expect(planner.pendingOption).toBeNull()
	})

	it('keep going when the switch is called off', () => {
		const planner = searched()
		planner.applyEdit(route(8_000), route(8_300), [TAVLEBORG])
		planner.selectOption(2)

		planner.cancelOption()

		expect(planner.selectedOption).toBe(0)
		expect(planner.editedRoute?.properties.length_m).toBe(8_300)
		expect(planner.pendingOption).toBeNull()
	})

	it('leave the saved route the only one, until the next search', () => {
		const planner = searched()
		planner.selectOption(1)

		planner.markSaved(42, route(8_000))
		expect(planner.saved?.id).toBe(42)
		expect(planner.isChosen).toBe(true)

		planner.findRoutes()
		expect(planner.saved).toBeNull()
		expect(planner.isChosen).toBe(false)
	})

	it('are gone with the next search', () => {
		const planner = searched()
		planner.applyEdit(route(8_000), route(8_300), [TAVLEBORG])

		planner.findRoutes()

		expect(planner.edit).toBeNull()
	})
})

describe('loadPlan', () => {
	it('sets the planner up as a saved route was planned, and finds routes again', () => {
		const planner = usePlannerStore()

		planner.loadPlan({
			activity: 'cycling',
			shape: 'point_to_point',
			start: UMEA,
			finish: TAVLEBORG,
			targetDistanceM: null,
			preferences: { green: 0.5 },
			waypoints: [{ lon: 20.28, lat: 63.825, at: 'after', after_m: 3_000 }],
		})

		expect(planner.routeRequest).toEqual({
			activity: 'cycling',
			shape: 'point_to_point',
			start: UMEA,
			finish: TAVLEBORG,
			preferences: { green: 0.5 },
			waypoints: [{ lon: 20.28, lat: 63.825, at: 'after', after_m: 3_000 }],
		})
		expect(planner.search?.request).toEqual(planner.routeRequest)
	})

	it('takes a loop with its distance', () => {
		const planner = usePlannerStore()

		planner.loadPlan({
			activity: 'running',
			shape: 'loop',
			start: UMEA,
			finish: UMEA,
			targetDistanceM: 8_000,
			preferences: {},
			waypoints: [],
		})

		expect(planner.routeRequest).toMatchObject({ shape: 'loop', target_distance_m: 8_000 })
		expect(planner.routeRequest).not.toHaveProperty('finish')
	})
})

describe('stored defaults', () => {
	it('become the weights while the sliders are untouched', () => {
		const planner = usePlannerStore()

		planner.receiveDefaults({ green: 0.5, water: -0.25 })

		expect(planner.preferenceWeights).toEqual({ green: 0.5, water: -0.25 })
		expect(planner.differsFromDefaults).toBe(false)
	})

	it('follow a later change, such as a nudge from a route review, if nothing was moved', () => {
		const planner = usePlannerStore()
		planner.receiveDefaults({ green: 0.5 })

		planner.receiveDefaults({ green: 0.6 })

		expect(planner.weightOf('green')).toBe(0.6)
	})

	it('never overwrite sliders the user moved', () => {
		const planner = usePlannerStore()
		planner.receiveDefaults({ green: 0.5 })
		planner.setWeight('water', 1)

		planner.receiveDefaults({ green: 0.6 })

		expect(planner.preferenceWeights).toEqual({ green: 0.5, water: 1 })
		expect(planner.differsFromDefaults).toBe(true)
	})

	it('can be gone back to', () => {
		const planner = usePlannerStore()
		planner.receiveDefaults({ green: 0.5 })
		planner.setWeight('green', 1)
		planner.setWeight('water', -0.5)

		planner.backToDefaults()

		expect(planner.preferenceWeights).toEqual({ green: 0.5 })
	})

	it('are forgotten with what was moved, so the next user starts from their own', () => {
		const planner = usePlannerStore()
		planner.receiveDefaults({ green: 0.5 })
		planner.setWeight('water', 1)

		planner.forgetDefaults()
		planner.receiveDefaults({ quiet_streets: 0.3 })

		expect(planner.preferenceWeights).toEqual({ quiet_streets: 0.3 })
	})

	it('are not there to differ from before they have loaded', () => {
		const planner = usePlannerStore()
		planner.setWeight('green', 1)

		expect(planner.differsFromDefaults).toBe(false)
	})
})
