import { describe, expect, it } from 'vitest'
import { ref } from 'vue'

import { settleStop, sheetStops, useSheetDrag } from './useSheetDrag'

const STOPS = [144, 422, 772]

describe('settleStop', () => {
	it('goes to the nearest stop after a slow drag', () => {
		expect(settleStop(STOPS, 200, 0)).toBe(0)
		expect(settleStop(STOPS, 300, 0.1)).toBe(1)
		expect(settleStop(STOPS, 700, -0.1)).toBe(2)
	})

	it('goes on to the next stop in the direction of a flick', () => {
		expect(settleStop(STOPS, 160, 1)).toBe(1)
		expect(settleStop(STOPS, 760, -1)).toBe(1)
		expect(settleStop(STOPS, 430, 1)).toBe(2)
	})

	it('stays at the end when flicked past it', () => {
		expect(settleStop(STOPS, 772, 1)).toBe(2)
		expect(settleStop(STOPS, 144, -1)).toBe(0)
	})
})

describe('useSheetDrag', () => {
	function pointer(clientY: number, timeStamp: number) {
		const target = { setPointerCapture: () => {}, releasePointerCapture: () => {} }
		return {
			clientY,
			timeStamp,
			pointerId: 1,
			currentTarget: target,
		} as unknown as PointerEvent
	}

	it('follows the pointer, then settles on a stop', () => {
		const stop = ref(0)
		const drag = useSheetDrag(ref(STOPS), stop)

		drag.onPointerDown(pointer(700, 0))
		drag.onPointerMove(pointer(500, 400))
		expect(drag.heightPx.value).toBe(344)
		expect(drag.isDragging.value).toBe(true)

		drag.onPointerUp(pointer(500, 800))
		expect(stop.value).toBe(1)
		expect(drag.heightPx.value).toBe(422)
		expect(drag.isDragging.value).toBe(false)
	})

	it('does not drag past the first or last stop', () => {
		const drag = useSheetDrag(ref(STOPS), ref(0))

		drag.onPointerDown(pointer(700, 0))
		drag.onPointerMove(pointer(900, 100))
		expect(drag.heightPx.value).toBe(144)
		drag.onPointerMove(pointer(-500, 200))
		expect(drag.heightPx.value).toBe(772)
	})

	it('treats a press without movement as a tap, not a drag', () => {
		const stop = ref(0)
		const drag = useSheetDrag(ref(STOPS), stop)

		drag.onPointerDown(pointer(700, 0))
		drag.onPointerMove(pointer(698, 50))
		expect(drag.onPointerUp(pointer(698, 100))).toBe(false)
		expect(stop.value).toBe(0)
	})
})

describe('sheetStops', () => {
	it('stops at the peek, half the screen and nearly all of it', () => {
		expect(sheetStops(208, 844, 72)).toEqual([208, 422, 772])
	})

	it('keeps the middle stop above a peek taller than half the screen', () => {
		expect(sheetStops(500, 844, 72)).toEqual([500, 500, 772])
	})

	it('never peeks above the highest stop', () => {
		expect(sheetStops(900, 844, 72)).toEqual([772, 772, 772])
	})
})
