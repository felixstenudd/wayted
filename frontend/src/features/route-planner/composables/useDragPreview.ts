import { onScopeDispose, shallowRef, watch, type Ref, type ShallowRef } from 'vue'

import { distanceM, type LonLat } from '@/features/map'

// How long the pointer rests before a preview is asked for.
export const PAUSE_MS = 150
// The edit window grows with the drag, so long drags take long to route; they are not previewed.
const MAX_DRAG_M = 1_500
// A preview that took longer than this ends previewing for the drag; it would lag the pointer.
const SLOW_MS = 300
// A drop this near the spot last previewed takes that preview as it is.
const SAME_SPOT_M = 5

/**
 * Previews of a drag from grab to pointer while it goes on: when the pointer rests, fetch is
 * asked for that spot, one request at a time. answer is the latest preview, until the drag ends.
 */
export function useDragPreview<Answer>(
	grab: Readonly<Ref<LonLat | null>>,
	pointer: Readonly<Ref<LonLat | null>>,
	fetch: (grab: LonLat, drop: LonLat) => Promise<Answer>,
): { answer: ShallowRef<Answer | null>; answerFor: (drop: LonLat) => Answer | null } {
	const answer = shallowRef<Answer | null>(null)
	let answeredFor: LonLat | null = null
	let timer: ReturnType<typeof setTimeout> | undefined
	let isAsking = false
	let queued: LonLat | null = null
	let isSlow = false
	// Answers to an earlier drag are let go.
	let drag = 0

	function ask(from: LonLat, at: LonLat): void {
		if (isAsking) {
			queued = at
			return
		}
		isAsking = true
		const startedAt = Date.now()
		const thisDrag = drag
		fetch(from, at)
			.then((answered) => {
				if (thisDrag !== drag) return
				isSlow ||= Date.now() - startedAt > SLOW_MS
				answer.value = answered
				answeredFor = at
			})
			.catch(() => {
				// A preview that fails shows nothing; the drop makes the edit and says why.
			})
			.finally(() => {
				isAsking = false
				const next = queued
				queued = null
				if (next && thisDrag === drag && !isSlow) ask(from, next)
			})
	}

	watch([grab, pointer], ([from, at]) => {
		clearTimeout(timer)
		if (!from || !at) {
			drag += 1
			answer.value = null
			answeredFor = null
			queued = null
			isSlow = false
			return
		}
		if (isSlow) return
		if (distanceM(from, at) > MAX_DRAG_M) {
			answer.value = null
			answeredFor = null
			return
		}
		timer = setTimeout(() => ask(from, at), PAUSE_MS)
	})
	onScopeDispose(() => clearTimeout(timer))

	function answerFor(drop: LonLat): Answer | null {
		return answeredFor && distanceM(answeredFor, drop) <= SAME_SPOT_M ? answer.value : null
	}

	return { answer, answerFor }
}
