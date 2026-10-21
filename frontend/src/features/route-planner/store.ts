import { defineStore } from 'pinia'
import { computed, readonly, ref, watch } from 'vue'

import type { LonLat } from '@/features/map'

import type {
	Activity,
	DistanceRange,
	MissingPoint,
	RouteRequest,
	RouteSearch,
	RouteShape,
	ThroughPoint,
	ThroughPointPlacement,
} from './types'

export const DISTANCE_RANGES: Record<Activity, DistanceRange> = {
	running: { minKm: 1, maxKm: 50, defaultKm: 5 },
	cycling: { minKm: 5, maxKm: 200, defaultKm: 25 },
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

/** Whether two sets of weights say the same; a missing weight is "don't mind". */
function sameWeights(a: Record<string, number>, b: Record<string, number>): boolean {
	const keys = new Set([...Object.keys(a), ...Object.keys(b)])
	return [...keys].every((key) => (a[key] ?? 0) === (b[key] ?? 0))
}

/** The route the user is setting up, and the search for it once they ask. */
export const usePlannerStore = defineStore('route-planner', () => {
	const activity = ref<Activity>('running')
	const shape = ref<RouteShape>('loop')
	const start = ref<LonLat | null>(null)
	// Kept while a loop is chosen, so switching back to point to point restores it.
	const finish = ref<LonLat | null>(null)
	const targetDistanceKm = ref(DISTANCE_RANGES.running.defaultKm)
	// From point to point the route may instead be the most pleasant way, however long. A loop
	// always has a distance; this is kept for when point to point is chosen again.
	const hasTargetDistance = ref(true)
	// In the order added, which the planner keeps only for points placed as soon as possible.
	const throughPoints = ref<ThroughPoint[]>([])
	let throughPointIds = 0
	// The through point whose settings are open, on the map or in the sheet.
	const editingThroughPointId = ref<number | null>(null)
	// Only weights other than 0 ("don't mind") are kept.
	const preferenceWeights = ref<Record<string, number>>({})
	// The user's stored weights, once loaded; the planner starts from them.
	const defaultWeights = ref<Record<string, number> | null>(null)
	// The last press of Find routes, until the request changes.
	const search = ref<RouteSearch | null>(null)
	let searches = 0

	const distanceRange = computed(() => DISTANCE_RANGES[activity.value])
	const usesTargetDistance = computed(() => shape.value === 'loop' || hasTargetDistance.value)
	const setWeightCount = computed(() => Object.keys(preferenceWeights.value).length)
	const differsFromDefaults = computed(
		() =>
			defaultWeights.value !== null &&
			!sameWeights(preferenceWeights.value, defaultWeights.value),
	)

	const missingPoint = computed<MissingPoint>(() => {
		if (start.value === null) return 'start'
		if (shape.value === 'point_to_point' && finish.value === null) return 'finish'
		return null
	})

	const routeRequest = computed<RouteRequest | null>(() => {
		if (missingPoint.value !== null || start.value === null) return null
		return {
			activity: activity.value,
			shape: shape.value,
			start: start.value,
			...(shape.value === 'point_to_point' && finish.value ? { finish: finish.value } : {}),
			...(usesTargetDistance.value
				? { target_distance_m: Math.round(targetDistanceKm.value * 1000) }
				: {}),
			preferences: { ...preferenceWeights.value },
			waypoints: throughPoints.value.map(({ lonLat, placement }) => ({
				...lonLat,
				at: placement.at,
				...(placement.at === 'after'
					? { after_m: Math.round(placement.afterKm * 1000) }
					: {}),
			})),
		}
	})

	// A route found for other settings is stale. Sync, so a change and a search in one tick
	// keep the search.
	watch(
		routeRequest,
		() => {
			search.value = null
		},
		{ flush: 'sync' },
	)

	/** Starts a search for the current request. Returns false when points are missing. */
	function findRoutes(): boolean {
		if (routeRequest.value === null) return false
		searches += 1
		search.value = { id: searches, request: routeRequest.value, startedAt: Date.now() }
		return true
	}

	function setActivity(next: Activity): void {
		activity.value = next
		const { minKm, maxKm, defaultKm } = distanceRange.value
		if (targetDistanceKm.value < minKm || targetDistanceKm.value > maxKm) {
			targetDistanceKm.value = defaultKm
		}
	}

	/**
	 * Puts a map click on the first point still missing, then adds through points. While a route
	 * is shown a click adds nothing, so a stray one does not throw the route away. Returns whether
	 * the click placed anything.
	 */
	function placeNextPoint(at: LonLat): boolean {
		if (missingPoint.value === 'start') start.value = at
		else if (missingPoint.value === 'finish') finish.value = at
		else if (search.value === null) addThroughPoint(at)
		else return false
		return true
	}

	/** Returns the new point's id. */
	function addThroughPoint(at: LonLat): number {
		throughPointIds += 1
		throughPoints.value = [
			...throughPoints.value,
			{ id: throughPointIds, lonLat: at, placement: { at: 'any' } },
		]
		return throughPointIds
	}

	function moveThroughPoint(id: number, to: LonLat): void {
		throughPoints.value = throughPoints.value.map((point) =>
			point.id === id ? { ...point, lonLat: to } : point,
		)
	}

	function setThroughPointPlacement(id: number, placement: ThroughPointPlacement): void {
		throughPoints.value = throughPoints.value.map((point) =>
			point.id === id ? { ...point, placement } : point,
		)
	}

	function removeThroughPoint(id: number): void {
		throughPoints.value = throughPoints.value.filter((point) => point.id !== id)
		if (editingThroughPointId.value === id) editingThroughPointId.value = null
	}

	function clearThroughPoints(): void {
		throughPoints.value = []
		editingThroughPointId.value = null
	}

	function editThroughPoint(id: number | null): void {
		editingThroughPointId.value = id
	}

	function setTargetDistanceKm(km: number): void {
		const { minKm, maxKm } = distanceRange.value
		targetDistanceKm.value = Math.round(clamp(km, minKm, maxKm) * 10) / 10
	}

	function weightOf(key: string): number {
		return preferenceWeights.value[key] ?? 0
	}

	function setWeight(key: string, weight: number): void {
		const rounded = Math.round(clamp(weight, -1, 1) * 100) / 100
		if (rounded === 0) resetWeight(key)
		else preferenceWeights.value = { ...preferenceWeights.value, [key]: rounded }
	}

	function resetWeight(key: string): void {
		const rest = { ...preferenceWeights.value }
		delete rest[key]
		preferenceWeights.value = rest
	}

	/**
	 * Takes in the stored weights. Sliders nobody has moved follow them, also when they change
	 * later, such as after a route review; sliders the user moved are left as they are.
	 */
	function receiveDefaults(weights: Record<string, number>): void {
		const isUntouched =
			defaultWeights.value === null
				? setWeightCount.value === 0
				: sameWeights(preferenceWeights.value, defaultWeights.value)
		defaultWeights.value = { ...weights }
		if (isUntouched) preferenceWeights.value = { ...weights }
	}

	function backToDefaults(): void {
		if (defaultWeights.value) preferenceWeights.value = { ...defaultWeights.value }
	}

	/** Drops the weights a signed-in user brought, so whoever comes next starts clean. */
	function forgetDefaults(): void {
		defaultWeights.value = null
		preferenceWeights.value = {}
	}

	return {
		activity: readonly(activity),
		shape,
		start,
		finish,
		targetDistanceKm: readonly(targetDistanceKm),
		hasTargetDistance,
		usesTargetDistance,
		throughPoints: readonly(throughPoints),
		editingThroughPointId: readonly(editingThroughPointId),
		preferenceWeights: readonly(preferenceWeights),
		distanceRange,
		setWeightCount,
		differsFromDefaults,
		missingPoint,
		routeRequest,
		search: readonly(search),
		findRoutes,
		setActivity,
		placeNextPoint,
		addThroughPoint,
		moveThroughPoint,
		setThroughPointPlacement,
		removeThroughPoint,
		clearThroughPoints,
		editThroughPoint,
		setTargetDistanceKm,
		weightOf,
		setWeight,
		resetWeight,
		receiveDefaults,
		backToDefaults,
		forgetDefaults,
	}
})
