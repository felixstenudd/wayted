import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, useTemplateRef } from 'vue'

import { provideMap, useMapContext, type MapContext } from '../context'
import { useMap, type MapViewOptions } from './useMap'

// jsdom has no WebGL, so MapLibre's map is replaced by one that only keeps listeners.
const { FakeMap, maps } = vi.hoisted(() => {
	type Listener = (event: unknown) => void
	const maps: FakeMap[] = []
	class FakeMap {
		style: unknown
		keyboard = { disableRotation: vi.fn() }
		touchZoomRotate = { disableRotation: vi.fn() }
		private listeners = new Map<string, Listener[]>()

		constructor(readonly options: Record<string, unknown>) {
			this.style = options.style
			maps.push(this)
		}

		on(type: string, listener: Listener) {
			this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
		}

		once(type: string, listener: Listener) {
			const first: Listener = (event) => {
				this.listeners.set(
					type,
					(this.listeners.get(type) ?? []).filter((other) => other !== first),
				)
				listener(event)
			}
			this.on(type, first)
		}

		fire(type: string, event: unknown = {}) {
			for (const listener of this.listeners.get(type) ?? []) listener(event)
		}

		setStyle(style: unknown) {
			this.style = style
		}

		addControl = vi.fn()
		remove() {}
	}
	return { FakeMap, maps }
})
vi.mock('maplibre-gl', () => ({
	Map: FakeMap,
	NavigationControl: class {},
	ScaleControl: class {},
	setWorkerUrl: () => {},
}))
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url', () => ({ default: 'worker.js' }))

const STYLE_URL = 'https://tiles.example/style.json'
const EMPTY_STYLE = { version: 8, sources: {}, layers: [] }

let host: VueWrapper | null = null

function mountMap(options: Partial<MapViewOptions> = {}) {
	let context!: MapContext
	const MapHost = defineComponent({
		setup() {
			context = useMapContext()
			const container = useTemplateRef<HTMLElement>('container')
			useMap(container, { center: { lon: 18, lat: 59 }, zoom: 13, ...options })
			return () => h('div', { ref: 'container' })
		},
	})
	// provideMap has to be called by a parent of the component that holds the map
	host = mount({
		setup() {
			provideMap()
			return () => h(MapHost)
		},
	})
	const map = maps.at(-1)
	if (!map) throw new Error('No map was created.')
	return { context, map }
}

beforeEach(() => {
	vi.stubEnv('VITE_MAP_STYLE_URL', STYLE_URL)
})

afterEach(() => {
	host?.unmount()
	maps.length = 0
	vi.unstubAllEnvs()
	vi.restoreAllMocks()
})

describe('useMap', () => {
	it('is ready as soon as the style is loaded, before any tile', () => {
		const { context, map } = mountMap()
		expect(context.isReady.value).toBe(false)

		map.fire('style.load')

		expect(context.isReady.value).toBe(true)
		expect(context.hasBaseMapFailed.value).toBe(false)
	})

	it('keeps north up: no rotating or tilting, by mouse, touch or keyboard', () => {
		const { map } = mountMap()

		expect(map.options).toMatchObject({ dragRotate: false, touchPitch: false })
		expect(map.keyboard.disableRotation).toHaveBeenCalled()
		expect(map.touchZoomRotate.disableRotation).toHaveBeenCalled()
	})

	it('puts the zoom buttons top right unless told otherwise', () => {
		const positions = (map: InstanceType<typeof FakeMap>) =>
			map.addControl.mock.calls.map(([, position]: unknown[]) => position)

		expect(positions(mountMap().map)).toEqual(['top-right', 'bottom-right'])
		host?.unmount()
		expect(positions(mountMap({ zoomButtonsPosition: 'bottom-right' }).map)).toEqual([
			'bottom-right',
			'bottom-right',
		])
	})

	it('folds shown compact credits into their button five seconds after loading', () => {
		vi.useFakeTimers()
		try {
			const { map } = mountMap()
			const credits = document.createElement('details')
			credits.className = 'maplibregl-ctrl-attrib maplibregl-compact maplibregl-compact-show'
			host?.element.append(credits)

			map.fire('load')
			vi.advanceTimersByTime(4999)
			expect(credits.classList.contains('maplibregl-compact-show')).toBe(true)
			vi.advanceTimersByTime(1)
			expect(credits.classList.contains('maplibregl-compact-show')).toBe(false)
		} finally {
			vi.useRealTimers()
		}
	})

	it('says so and draws on an empty map when no style URL is set', () => {
		vi.stubEnv('VITE_MAP_STYLE_URL', '')

		const { context, map } = mountMap()
		map.fire('style.load')

		expect(map.style).toEqual(EMPTY_STYLE)
		expect(context.hasBaseMapFailed.value).toBe(true)
		expect(context.isReady.value).toBe(true)
	})

	it('falls back to an empty map when the style does not load', () => {
		const { context, map } = mountMap()

		map.fire('error', { error: new Error('404') })

		expect(context.hasBaseMapFailed.value).toBe(true)
		expect(map.style).toEqual(EMPTY_STYLE)
	})

	it('keeps the base map and logs what fails after the style has loaded', () => {
		const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
		const tileError = new Error('tile 503')
		const { context, map } = mountMap()
		map.fire('style.load')

		map.fire('error', { error: tileError })

		expect(context.hasBaseMapFailed.value).toBe(false)
		expect(map.style).toBe(STYLE_URL)
		expect(logged).toHaveBeenCalledWith(tileError)
	})
})
