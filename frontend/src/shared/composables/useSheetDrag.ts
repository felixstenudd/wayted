import { computed, ref, type Ref } from 'vue'

// Faster than this when let go, a drag is a flick and goes on to the next stop.
const FLICK_PX_PER_MS = 0.5
// A pointer held still this long before letting go is not flicking.
const FLICK_WINDOW_MS = 100
// Movement under this is a shaky tap, not a drag.
const TAP_SLOP_PX = 6

/** The stop a sheet settles on when let go at heightPx. Velocity is positive when growing. */
export function settleStop(stops: readonly number[], heightPx: number, velocity: number): number {
	if (velocity >= FLICK_PX_PER_MS) {
		const next = stops.findIndex((stop) => stop > heightPx + 1)
		return next === -1 ? stops.length - 1 : next
	}
	if (velocity <= -FLICK_PX_PER_MS) {
		for (let index = stops.length - 1; index >= 0; index--) {
			if ((stops[index] ?? 0) < heightPx - 1) return index
		}
		return 0
	}
	let nearest = 0
	stops.forEach((stop, index) => {
		if (Math.abs(stop - heightPx) < Math.abs((stops[nearest] ?? 0) - heightPx)) nearest = index
	})
	return nearest
}

/**
 * A sheet's stop heights in px, lowest first: the peek, half the screen, and all of it but a gap
 * at the top. A tall peek pushes the middle stop up with it, and never goes past the highest.
 */
export function sheetStops(peekPx: number, viewportPx: number, topGapPx: number): number[] {
	const highest = viewportPx - topGapPx
	const lowest = Math.min(peekPx, highest)
	return [lowest, Math.max(viewportPx / 2, lowest), highest]
}

/** Drags a sheet between stops (heights in px, lowest first) and settles on one when let go. */
export function useSheetDrag(stops: Readonly<Ref<readonly number[]>>, stop: Ref<number>) {
	const dragHeightPx = ref<number | null>(null)
	const heightPx = computed(() => dragHeightPx.value ?? stops.value[stop.value] ?? 0)
	const isDragging = computed(() => dragHeightPx.value !== null)

	let start: { y: number; heightPx: number } | null = null
	let last = { y: 0, time: 0 }
	let velocity = 0

	function onPointerDown(event: PointerEvent): void {
		;(event.currentTarget as Element).setPointerCapture(event.pointerId)
		start = { y: event.clientY, heightPx: heightPx.value }
		last = { y: event.clientY, time: event.timeStamp }
		velocity = 0
	}

	function onPointerMove(event: PointerEvent): void {
		if (start === null) return
		if (dragHeightPx.value === null && Math.abs(event.clientY - start.y) < TAP_SLOP_PX) return
		const elapsedMs = event.timeStamp - last.time
		if (elapsedMs > 0) velocity = (last.y - event.clientY) / elapsedMs
		last = { y: event.clientY, time: event.timeStamp }
		const lowest = stops.value[0] ?? 0
		const highest = stops.value.at(-1) ?? lowest
		const height = start.heightPx + start.y - event.clientY
		dragHeightPx.value = Math.min(Math.max(height, lowest), highest)
	}

	/** Returns whether the press was a drag, so the caller can ignore the click that follows. */
	function onPointerUp(event: PointerEvent): boolean {
		if (start === null) return false
		start = null
		;(event.currentTarget as Element).releasePointerCapture(event.pointerId)
		if (dragHeightPx.value === null) return false
		const isFlick = event.timeStamp - last.time <= FLICK_WINDOW_MS
		stop.value = settleStop(stops.value, dragHeightPx.value, isFlick ? velocity : 0)
		dragHeightPx.value = null
		return true
	}

	return { heightPx, isDragging, onPointerDown, onPointerMove, onPointerUp }
}
