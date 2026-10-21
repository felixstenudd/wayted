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
} from './types'

export const DISTANCE_RANGES: Record<Activity, DistanceRange> = {
	running: { minKm: 1, maxKm: 50, defaultKm: 5 },
	cycling: { minKm: 5, maxKm: 200, defaultKm: 25 },
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

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
	// Only weights other than 0 ("don't mind") are kept.
	const preferenceWeights = ref<Record<string, number>>({})
	// The last press of Find routes, until the request changes.
	const search = ref<RouteSearch | null>(null)
	let searches = 0

	const distanceRange = computed(() => DISTANCE_RANGES[activity.value])
	const usesTargetDistance = computed(() => shape.value === 'loop' || hasTargetDistance.value)
	const setWeightCount = computed(() => Object.keys(preferenceWeights.value).length)

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

	/** Puts a map click on the first point still missing. Returns false when none is. */
	function placeNextPoint(at: LonLat): boolean {
		if (missingPoint.value === 'start') start.value = at
		else if (missingPoint.value === 'finish') finish.value = at
		else return false
		return true
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

	function resetWeights(): void {
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
		preferenceWeights: readonly(preferenceWeights),
		distanceRange,
		setWeightCount,
		missingPoint,
		routeRequest,
		search: readonly(search),
		findRoutes,
		setActivity,
		placeNextPoint,
		setTargetDistanceKm,
		weightOf,
		setWeight,
		resetWeight,
		resetWeights,
	}
})
