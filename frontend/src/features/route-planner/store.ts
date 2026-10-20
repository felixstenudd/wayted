import { defineStore } from 'pinia'
import { computed, readonly, ref } from 'vue'

import type { LonLat } from '@/features/map'

import type { Activity, DistanceRange, MissingPoint, RouteRequest, RouteShape } from './types'

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

/** The route the user is setting up, before any routes are found. */
export const usePlannerStore = defineStore('route-planner', () => {
	const activity = ref<Activity>('running')
	const shape = ref<RouteShape>('loop')
	const start = ref<LonLat | null>(null)
	// Kept while a loop is chosen, so switching back to point to point restores it.
	const finish = ref<LonLat | null>(null)
	const targetDistanceKm = ref(DISTANCE_RANGES.running.defaultKm)
	// Only weights other than 0 ("don't mind") are kept.
	const preferenceWeights = ref<Record<string, number>>({})
	// The user's stored weights, once loaded; the planner starts from them.
	const defaultWeights = ref<Record<string, number> | null>(null)

	const distanceRange = computed(() => DISTANCE_RANGES[activity.value])
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
			target_distance_m: Math.round(targetDistanceKm.value * 1000),
			preferences: { ...preferenceWeights.value },
		}
	})

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
		preferenceWeights: readonly(preferenceWeights),
		distanceRange,
		setWeightCount,
		differsFromDefaults,
		missingPoint,
		routeRequest,
		setActivity,
		placeNextPoint,
		setTargetDistanceKm,
		weightOf,
		setWeight,
		resetWeight,
		receiveDefaults,
		backToDefaults,
		forgetDefaults,
	}
})
