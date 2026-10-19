import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { useDetentPointer } from './useDetentPointer'

const DETENTS = [-1, -0.5, 0, 0.5, 1]
// A 200 px track from x = 100 to 300: 0 is at 200, each detent 50 px apart.
const TRACK = { left: 100, width: 200 } as DOMRect

function pointer(clientX: number) {
	const target = { setPointerCapture: () => {}, releasePointerCapture: () => {} }
	return { clientX, pointerId: 1, currentTarget: target } as unknown as PointerEvent
}

function setup(start = 0) {
	const value = ref(start)
	const slider = useDetentPointer(DETENTS, value, () => TRACK)
	return { value, slider }
}

beforeEach(() => {
	vi.useFakeTimers()
})

afterEach(() => {
	vi.useRealTimers()
})

describe('useDetentPointer', () => {
	it('jumps to the detent nearest a press on the track', () => {
		const { value, slider } = setup()

		slider.onPointerDown(pointer(262))
		slider.onPointerUp(pointer(262))

		expect(value.value).toBe(0.5)
	})

	it('snaps from detent to detent while dragging', () => {
		const { value, slider } = setup()

		slider.onPointerDown(pointer(200))
		slider.onPointerMove(pointer(235))
		expect(value.value).toBe(0.5)
		slider.onPointerMove(pointer(140))
		expect(value.value).toBe(-0.5)
		slider.onPointerUp(pointer(140))
		expect(value.value).toBe(-0.5)
	})

	it('fine-tunes in 0.01 steps at a quarter of the pointer speed after holding still', () => {
		const { value, slider } = setup()

		slider.onPointerDown(pointer(250))
		vi.advanceTimersByTime(400)
		expect(slider.isFine.value).toBe(true)
		// 20 px is 0.2 on this track, a quarter of that is 0.05.
		slider.onPointerMove(pointer(270))
		expect(value.value).toBe(0.55)
		slider.onPointerMove(pointer(254))
		expect(value.value).toBe(0.51)
		slider.onPointerUp(pointer(254))

		expect(value.value).toBe(0.51)
		expect(slider.isFine.value).toBe(false)
	})

	it('restarts the hold whenever the pointer moves on', () => {
		const { slider } = setup()

		slider.onPointerDown(pointer(200))
		vi.advanceTimersByTime(300)
		slider.onPointerMove(pointer(230))
		vi.advanceTimersByTime(300)
		expect(slider.isFine.value).toBe(false)
		vi.advanceTimersByTime(100)
		expect(slider.isFine.value).toBe(true)
	})

	it('does not count a small wobble as moving on', () => {
		const { value, slider } = setup()

		slider.onPointerDown(pointer(250))
		vi.advanceTimersByTime(300)
		slider.onPointerMove(pointer(252))
		vi.advanceTimersByTime(100)

		expect(slider.isFine.value).toBe(true)
		expect(value.value).toBe(0.5)
	})

	it('keeps a fine-tuned value when the thumb itself is grabbed', () => {
		// 0.37 sits at x = 237.
		const { value, slider } = setup(0.37)

		slider.onPointerDown(pointer(240))
		slider.onPointerUp(pointer(240))

		expect(value.value).toBe(0.37)
	})

	it('snaps a fine-tuned value when the thumb is dragged without holding', () => {
		const { value, slider } = setup(0.37)

		slider.onPointerDown(pointer(237))
		slider.onPointerMove(pointer(290))
		slider.onPointerUp(pointer(290))

		expect(value.value).toBe(1)
	})

	it('stops the hold timer when let go', () => {
		const { slider } = setup()

		slider.onPointerDown(pointer(200))
		slider.onPointerUp(pointer(200))
		vi.advanceTimersByTime(1000)

		expect(slider.isFine.value).toBe(false)
	})
})
