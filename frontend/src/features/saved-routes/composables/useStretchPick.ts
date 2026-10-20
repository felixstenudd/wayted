import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { LonLat } from '@/features/map'

import { useSavedRoute } from '../api'
import { useSavedRoutesStore } from '../store'
import { junctions, nearestJunction, orderedStretch, stretchLengthM, stretchLine } from '../stretch'

// A click further than this from every junction missed the route.
const MAX_REACH_M = 150

/** The stretch being picked on one route, for the panel and the map alike. */
export function useStretchPick(routeId: MaybeRefOrGetter<number>) {
	const saved = useSavedRoute(() => toValue(routeId))
	const store = useSavedRoutesStore()

	const coordinates = computed(() => saved.data.value?.geometry.coordinates ?? [])
	const all = computed(() => junctions(saved.data.value?.edges ?? []))

	const step = computed<'start' | 'end' | 'adjust' | null>(() => {
		const ends = store.stretchEnds
		if (!ends) return null
		if (ends.start === null) return 'start'
		return ends.end === null ? 'end' : 'adjust'
	})
	const stretch = computed(() => {
		const ends = store.stretchEnds
		if (!ends || ends.start === null || ends.end === null) return null
		return orderedStretch(ends.start, ends.end, all.value.length)
	})
	const line = computed(() =>
		stretch.value ? stretchLine(coordinates.value, all.value, stretch.value) : [],
	)
	const lengthM = computed(() => (stretch.value ? stretchLengthM(all.value, stretch.value) : 0))
	const pointOf = (junction: number): LonLat | null => {
		const [lon, lat] = coordinates.value[all.value[junction]?.point ?? -1] ?? []
		return lon === undefined || lat === undefined ? null : { lon, lat }
	}

	// The start, shown on its own until the end is placed.
	const lonePoint = computed(() =>
		step.value === 'end' ? pointOf(store.stretchEnds?.start ?? -1) : null,
	)

	function snap(at: LonLat, preferNear?: number): number | null {
		const hit = nearestJunction(coordinates.value, all.value, at, preferNear)
		return hit && hit.distanceM <= MAX_REACH_M ? hit.index : null
	}

	function setEnds(a: number, b: number): void {
		const { from, to } = orderedStretch(a, b, all.value.length)
		store.setStretchEnds({ start: from, end: to })
	}

	/** A click on the map: places the start, then the end, then moves whichever end is nearer. */
	function placeAt(at: LonLat): void {
		const ends = store.stretchEnds
		if (!ends) return
		if (ends.start === null) {
			const index = snap(at)
			if (index !== null) store.setStretchEnds({ start: index, end: null })
			return
		}
		const index = snap(at, ends.end ?? ends.start)
		if (index === null) return
		if (ends.end === null || !stretch.value) {
			setEnds(ends.start, index)
			return
		}
		const { from, to } = stretch.value
		if (Math.abs(index - from) <= Math.abs(index - to)) setEnds(index, to)
		else setEnds(from, index)
	}

	/** A handle dropped on the map, snapped to the junction nearest where it landed. */
	function moveEnd(which: 'from' | 'to', at: LonLat): void {
		if (!stretch.value) return
		const { from, to } = stretch.value
		const index = snap(at, which === 'from' ? from : to)
		if (index === null) setEnds(from, to)
		else if (which === 'from') setEnds(index, to)
		else setEnds(from, index)
	}

	/** From the sliders: an end moves, and never past the other. */
	function setFrom(index: number): void {
		if (stretch.value) setEnds(Math.min(index, stretch.value.to - 1), stretch.value.to)
	}

	function setTo(index: number): void {
		if (stretch.value) setEnds(stretch.value.from, Math.max(index, stretch.value.from + 1))
	}

	return {
		step,
		stretch,
		junctions: all,
		line,
		lengthM,
		pointOf,
		lonePoint,
		placeAt,
		moveEnd,
		setFrom,
		setTo,
	}
}
