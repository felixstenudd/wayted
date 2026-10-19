import { ref, type Ref } from 'vue'

import { nearestDetent, roundToHundredth, valueAtX, xOfValue } from '../utils/detents'

// Holding the pointer still this long switches to fine-tuning.
const HOLD_MS = 400
// Movement under this still counts as holding still.
const HOLD_SLOP_PX = 3
// While fine-tuning, the value moves at this share of the pointer's speed.
const FINE_GAIN = 0.25
// A press this close to the thumb grabs it instead of jumping to a detent.
const THUMB_REACH_PX = 10

/**
 * Pointer handling for a slider from -1 to 1. Dragging snaps to the detents;
 * holding still switches to fine-tuning in 0.01 steps until let go.
 */
export function useDetentPointer(
	detents: readonly number[],
	value: Ref<number>,
	track: () => DOMRect | null,
) {
	const isDragging = ref(false)
	const isFine = ref(false)

	let holdTimer: ReturnType<typeof setTimeout> | undefined
	let stillX = 0
	let fineFrom = { x: 0, value: 0 }

	function holdFrom(x: number): void {
		clearTimeout(holdTimer)
		stillX = x
		holdTimer = setTimeout(() => {
			isFine.value = true
			fineFrom = { x: stillX, value: value.value }
		}, HOLD_MS)
	}

	function onPointerDown(event: PointerEvent): void {
		const rect = track()
		if (!rect) return
		;(event.currentTarget as Element).setPointerCapture(event.pointerId)
		isDragging.value = true
		isFine.value = false
		const thumbX = xOfValue(value.value, rect.left, rect.width)
		if (Math.abs(event.clientX - thumbX) > THUMB_REACH_PX) {
			value.value = nearestDetent(valueAtX(event.clientX, rect.left, rect.width), detents)
		}
		holdFrom(event.clientX)
	}

	function onPointerMove(event: PointerEvent): void {
		const rect = track()
		if (!isDragging.value || !rect) return
		if (isFine.value) {
			const moved = ((event.clientX - fineFrom.x) / rect.width) * 2 * FINE_GAIN
			value.value = roundToHundredth(Math.min(Math.max(fineFrom.value + moved, -1), 1))
			return
		}
		if (Math.abs(event.clientX - stillX) <= HOLD_SLOP_PX) return
		value.value = nearestDetent(valueAtX(event.clientX, rect.left, rect.width), detents)
		holdFrom(event.clientX)
	}

	function onPointerUp(event: PointerEvent): void {
		clearTimeout(holdTimer)
		if (!isDragging.value) return
		;(event.currentTarget as Element).releasePointerCapture(event.pointerId)
		isDragging.value = false
		isFine.value = false
	}

	return { isDragging, isFine, onPointerDown, onPointerMove, onPointerUp }
}
