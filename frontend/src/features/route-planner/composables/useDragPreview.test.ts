import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'

import type { LonLat } from '@/features/map'

import { PAUSE_MS, useDragPreview } from './useDragPreview'

const GRAB = { lon: 20.26, lat: 63.82 }
// About 110 m north, and about 2.2 km north.
const NEAR = { lon: 20.26, lat: 63.821 }
const FAR = { lon: 20.26, lat: 63.84 }

beforeEach(() => {
	vi.useFakeTimers()
})
afterEach(() => {
	vi.useRealTimers()
})

function setup(answerAfterMs = 50) {
	const grab = ref<LonLat | null>(null)
	const pointer = ref<LonLat | null>(null)
	const fetch = vi.fn(
		(_grab: LonLat, drop: LonLat) =>
			new Promise<{ drop: LonLat }>((resolve) =>
				setTimeout(() => resolve({ drop }), answerAfterMs),
			),
	)
	const preview = useDragPreview(grab, pointer, fetch)
	return { grab, pointer, fetch, preview }
}

describe('useDragPreview', () => {
	it('asks for the spot the pointer rests on, once it has rested', async () => {
		const { grab, pointer, fetch, preview } = setup()
		grab.value = GRAB
		pointer.value = NEAR
		await nextTick()

		await vi.advanceTimersByTimeAsync(PAUSE_MS - 10)
		expect(fetch).not.toHaveBeenCalled()
		await vi.advanceTimersByTimeAsync(100)

		expect(fetch).toHaveBeenCalledWith(GRAB, NEAR)
		expect(preview.answer.value).toEqual({ drop: NEAR })
		expect(preview.answerFor(NEAR)).toEqual({ drop: NEAR })
		expect(preview.answerFor(FAR)).toBeNull()
	})

	it('leaves long drags alone, which take long to route', async () => {
		const { grab, pointer, fetch } = setup()
		grab.value = GRAB
		pointer.value = FAR
		await nextTick()

		await vi.advanceTimersByTimeAsync(1_000)

		expect(fetch).not.toHaveBeenCalled()
	})

	it('stops for the rest of the drag once a preview is slow', async () => {
		const { grab, pointer, fetch } = setup(400)
		grab.value = GRAB
		pointer.value = NEAR
		await nextTick()
		await vi.advanceTimersByTimeAsync(PAUSE_MS + 500)

		pointer.value = { lon: 20.261, lat: 63.821 }
		await nextTick()
		await vi.advanceTimersByTimeAsync(1_000)

		expect(fetch).toHaveBeenCalledTimes(1)
	})

	it('forgets its preview when the drag ends', async () => {
		const { grab, pointer, preview } = setup()
		grab.value = GRAB
		pointer.value = NEAR
		await nextTick()
		await vi.advanceTimersByTimeAsync(PAUSE_MS + 100)

		grab.value = null
		pointer.value = null
		await nextTick()

		expect(preview.answer.value).toBeNull()
	})
})
