import { mount, type VueWrapper } from '@vue/test-utils'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { provideMap, useMapContext } from '../context'
import { distanceM } from '../geometry'
import { useCircleDraw } from './useCircleDraw'

type Listener = (event: unknown) => void

// Only what useCircleDraw touches: listeners, panning and the cursor.
class FakeMap {
	dragPan = { enable: vi.fn(), disable: vi.fn() }
	private canvas = document.createElement('canvas')
	private listeners = new Map<string, Listener[]>()

	on(type: string, listener: Listener) {
		this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
	}

	off(type: string, listener: Listener) {
		this.listeners.set(
			type,
			(this.listeners.get(type) ?? []).filter((other) => other !== listener),
		)
	}

	fire(type: string, lon: number, lat: number, button = 0) {
		const event = { lngLat: { lng: lon, lat }, originalEvent: { button } }
		for (const listener of this.listeners.get(type) ?? []) listener(event)
	}

	getCanvas() {
		return this.canvas
	}
}

const MAX_RADIUS_M = 1000
const CENTER = { lon: 18, lat: 59 }
const NEARBY = { lon: 18, lat: 59.001 }

let host: VueWrapper | null = null

function mountDrawing(isActive = true) {
	const map = new FakeMap()
	let drawing!: ReturnType<typeof useCircleDraw>
	const Drawing = defineComponent({
		setup() {
			const context = useMapContext()
			context.map.value = map as unknown as MapLibreMap
			context.isReady.value = true
			drawing = useCircleDraw(ref(isActive), MAX_RADIUS_M)
			return () => null
		},
	})
	// provideMap has to be called by a parent of the component that draws
	host = mount({
		setup() {
			provideMap()
			return () => h(Drawing)
		},
	})
	return { map, circle: drawing.circle }
}

const release = () => window.dispatchEvent(new MouseEvent('mouseup'))

afterEach(() => {
	host?.unmount()
})

describe('useCircleDraw', () => {
	it('draws a circle from where the map is pressed to where the pointer is', () => {
		const { map, circle } = mountDrawing()

		map.fire('mousedown', CENTER.lon, CENTER.lat)
		map.fire('mousemove', NEARBY.lon, NEARBY.lat)
		release()

		expect(circle.value?.center).toEqual(CENTER)
		expect(circle.value?.radiusM).toBeCloseTo(distanceM(CENTER, NEARBY), 6)
	})

	it('stops at the largest radius', () => {
		const { map, circle } = mountDrawing()

		map.fire('mousedown', CENTER.lon, CENTER.lat)
		map.fire('mousemove', 19, 60)

		expect(circle.value?.radiusM).toBe(MAX_RADIUS_M)
	})

	it('stops following the pointer once the button is released', () => {
		const { map, circle } = mountDrawing()
		map.fire('mousedown', CENTER.lon, CENTER.lat)
		map.fire('mousemove', NEARBY.lon, NEARBY.lat)
		release()
		const drawn = circle.value

		map.fire('mousemove', 19, 60)

		expect(circle.value).toEqual(drawn)
	})

	it('ignores the other mouse buttons', () => {
		const { map, circle } = mountDrawing()

		map.fire('mousedown', CENTER.lon, CENTER.lat, 2)
		map.fire('mousemove', NEARBY.lon, NEARBY.lat, 2)

		expect(circle.value).toBeNull()
	})

	it('keeps the circle when the map is only clicked', () => {
		const { map, circle } = mountDrawing()
		map.fire('mousedown', CENTER.lon, CENTER.lat)
		map.fire('mousemove', NEARBY.lon, NEARBY.lat)
		release()
		const drawn = circle.value

		map.fire('mousedown', 18.5, 59.5)
		release()

		expect(circle.value).toEqual(drawn)
	})

	it('draws nothing while it is not active', () => {
		const { map, circle } = mountDrawing(false)

		map.fire('mousedown', CENTER.lon, CENTER.lat)
		map.fire('mousemove', NEARBY.lon, NEARBY.lat)

		expect(circle.value).toBeNull()
	})
})
