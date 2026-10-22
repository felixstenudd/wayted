import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderCourseImage } from './courseImage'

// jsdom has no WebGL or 2D canvas, so these cover what happens around the drawing: the hidden
// container, the map's options, and that both always go away. The drawing is checked in a browser.
const { FakeMap, maps } = vi.hoisted(() => {
	type Listener = (event: unknown) => void
	const maps: FakeMap[] = []
	class FakeMap {
		private listeners = new Map<string, Listener[]>()
		remove = vi.fn()

		constructor(readonly options: { container: HTMLElement } & Record<string, unknown>) {
			maps.push(this)
		}

		on(type: string, listener: Listener) {
			this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
		}

		once(type: string, listener: Listener) {
			this.on(type, listener)
		}

		fire(type: string, event: unknown = {}) {
			for (const listener of this.listeners.get(type) ?? []) listener(event)
		}
	}
	return { FakeMap, maps }
})
vi.mock('maplibre-gl', () => ({ Map: FakeMap, setWorkerUrl: () => {} }))
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url', () => ({ default: 'worker.js' }))

// Taller than wide, so the portrait frame.
const LINE = [
	[18.0, 59.3],
	[18.01, 59.33],
	[18.0, 59.35],
]

function lastMap() {
	const map = maps.at(-1)
	if (!map) throw new Error('No map was created.')
	return map
}

beforeEach(() => {
	vi.stubEnv('VITE_MAP_STYLE_URL', 'https://tiles.example/style.json')
})

afterEach(() => {
	maps.length = 0
	vi.useRealTimers()
	vi.unstubAllEnvs()
	document.body.replaceChildren()
})

describe('renderCourseImage', () => {
	it('draws in a hidden container of the chosen frame, at twice the pixels', () => {
		void renderCourseImage(LINE, { isLoop: false }).catch(() => {})
		const map = lastMap()

		const { container } = map.options
		expect(container.isConnected).toBe(true)
		expect(container.style.width).toBe('1080px')
		expect(container.style.height).toBe('1350px')
		expect(container.style.visibility).toBe('hidden')
		expect(container.getAttribute('aria-hidden')).toBe('true')
		expect(map.options).toMatchObject({
			style: 'https://tiles.example/style.json',
			bounds: [18.0, 59.3, 18.01, 59.35],
			fitBoundsOptions: { padding: { top: 108, bottom: 108, left: 86, right: 86 } },
			pixelRatio: 2,
			canvasContextAttributes: { preserveDrawingBuffer: true },
			interactive: false,
			attributionControl: false,
		})
		// Settles the rendering, so its timer does not outlive the test.
		map.fire('error', { error: new Error('done') })
	})

	it('makes no image without a base map style', async () => {
		vi.stubEnv('VITE_MAP_STYLE_URL', '')

		await expect(renderCourseImage(LINE, { isLoop: false })).rejects.toThrow()
		expect(maps).toHaveLength(0)
		expect(document.body.children).toHaveLength(0)
	})

	it('makes no image when the map fails, and cleans up', async () => {
		const failure = new Error('tile 503')
		const rendering = renderCourseImage(LINE, { isLoop: false })
		const map = lastMap()

		map.fire('error', { error: failure })

		await expect(rendering).rejects.toBe(failure)
		expect(map.remove).toHaveBeenCalled()
		expect(document.body.children).toHaveLength(0)
	})

	it('gives up when the map is not drawn within 15 s, and cleans up', async () => {
		vi.useFakeTimers()
		const rendering = renderCourseImage(LINE, { isLoop: false })
		const failed = expect(rendering).rejects.toThrow('in time')
		const map = lastMap()

		vi.advanceTimersByTime(15_000)

		await failed
		expect(map.remove).toHaveBeenCalled()
		expect(document.body.children).toHaveLength(0)
	})
})
