import type { MapLayerMouseEvent, MapMouseEvent } from 'maplibre-gl'
import { onScopeDispose, ref, type Ref } from 'vue'

import { onMap } from '../context'
import type { LonLat } from '../geometry'
import { isOnMarker } from './useMapClick'

// Less than this is a click that wobbled, not a drag.
const DRAG_PX = 4
// Let go this near where it was grabbed, a drag is called off.
const CANCEL_PX = 16

const lonLat = (event: MapMouseEvent): LonLat => ({ lon: event.lngLat.lng, lat: event.lngLat.lat })

/**
 * Lets a line of a layer be grabbed with the mouse and dragged: grab is where it was taken,
 * pointer where it is now, and onDrop gets both once it is let go after moving. Esc, or letting
 * go back where it was grabbed, calls the drag off. The map does not pan during the drag. hover
 * is where the pointer is while over the line, for a handle to show. While isEnabled says no, the
 * line cannot be grabbed.
 */
export function useMapLineDrag(
	layerId: string,
	onDrop: (grab: LonLat, drop: LonLat) => void,
	isEnabled: () => boolean = () => true,
): { grab: Ref<LonLat | null>; pointer: Ref<LonLat | null>; hover: Ref<LonLat | null> } {
	const grab = ref<LonLat | null>(null)
	const pointer = ref<LonLat | null>(null)
	const hover = ref<LonLat | null>(null)
	let pressedPx: { x: number; y: number } | null = null
	let pointerPx: { x: number; y: number } | null = null
	let hasMoved = false
	let canvas: HTMLElement | null = null

	const press = (event: MapLayerMouseEvent) => {
		// A marker over the line, such as the start, is dragged for itself.
		if (event.originalEvent.button !== 0 || isOnMarker(event) || !isEnabled()) return
		// Keeps the map from panning for this drag.
		event.preventDefault()
		grab.value = lonLat(event)
		pressedPx = event.point
		hasMoved = false
		if (canvas) canvas.style.cursor = 'grabbing'
	}
	const move = (event: MapMouseEvent) => {
		if (!grab.value || !pressedPx) return
		hasMoved ||= Math.hypot(event.point.x - pressedPx.x, event.point.y - pressedPx.y) > DRAG_PX
		pointerPx = event.point
		if (hasMoved) pointer.value = lonLat(event)
	}
	const over = (event: MapLayerMouseEvent) => {
		if (isOnMarker(event) || !isEnabled()) {
			out()
			return
		}
		hover.value = lonLat(event)
		if (canvas && !grab.value) canvas.style.cursor = 'grab'
	}
	const out = () => {
		hover.value = null
		if (canvas && !grab.value) canvas.style.cursor = ''
	}
	const end = () => {
		grab.value = null
		pointer.value = null
		pressedPx = null
		pointerPx = null
		if (canvas) canvas.style.cursor = hover.value ? 'grab' : ''
	}
	const release = () => {
		const isBack =
			pressedPx !== null &&
			pointerPx !== null &&
			Math.hypot(pointerPx.x - pressedPx.x, pointerPx.y - pressedPx.y) < CANCEL_PX
		if (grab.value && hasMoved && pointer.value && !isBack) onDrop(grab.value, pointer.value)
		end()
	}
	const cancel = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && grab.value) end()
	}

	onMap(
		(ready) => {
			canvas = ready.getCanvas()
			ready.on('mousedown', layerId, press)
			ready.on('mousemove', layerId, over)
			ready.on('mouseleave', layerId, out)
			ready.on('mousemove', move)
		},
		(ready) => {
			ready.off('mousedown', layerId, press)
			ready.off('mousemove', layerId, over)
			ready.off('mouseleave', layerId, out)
			ready.off('mousemove', move)
			ready.getCanvas().style.cursor = ''
		},
	)

	// On the window: a drag can end outside the map.
	window.addEventListener('mouseup', release)
	window.addEventListener('keydown', cancel)
	onScopeDispose(() => {
		window.removeEventListener('mouseup', release)
		window.removeEventListener('keydown', cancel)
	})

	return { grab, pointer, hover }
}

/** Shows a cursor while the pointer is over a layer's features, such as one that can be clicked. */
export function useMapLayerCursor(layerId: string, cursor: string): void {
	let canvas: HTMLElement | null = null
	const over = () => {
		if (canvas) canvas.style.cursor = cursor
	}
	const out = () => {
		if (canvas) canvas.style.cursor = ''
	}
	onMap(
		(ready) => {
			canvas = ready.getCanvas()
			ready.on('mouseenter', layerId, over)
			ready.on('mouseleave', layerId, out)
		},
		(ready) => {
			ready.off('mouseenter', layerId, over)
			ready.off('mouseleave', layerId, out)
		},
	)
}
