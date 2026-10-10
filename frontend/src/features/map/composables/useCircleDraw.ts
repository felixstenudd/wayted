import type { MapMouseEvent } from 'maplibre-gl'
import { onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import { onMap, useMapContext } from '../context'
import { distanceM, type Circle, type LonLat } from '../geometry'

/**
 * While active, pressing sets the centre of a circle and dragging sets its radius, up to
 * maxRadiusM. The map does not pan while active.
 */
export function useCircleDraw(
	isActive: MaybeRefOrGetter<boolean>,
	maxRadiusM: number,
): { circle: Ref<Circle | null> } {
	const { map, isReady } = useMapContext()
	const circle = ref<Circle | null>(null)
	// where the primary button went down; the circle only changes once the pointer moves
	let pressedAt: LonLat | null = null

	const press = (event: MapMouseEvent) => {
		if (!toValue(isActive) || event.originalEvent.button !== 0) return
		pressedAt = { lon: event.lngLat.lng, lat: event.lngLat.lat }
	}
	const drag = (event: MapMouseEvent) => {
		if (!pressedAt) return
		const to = { lon: event.lngLat.lng, lat: event.lngLat.lat }
		const radiusM = Math.min(distanceM(pressedAt, to), maxRadiusM)
		if (radiusM > 0) circle.value = { center: pressedAt, radiusM }
	}
	const release = () => {
		pressedAt = null
	}

	onMap(
		(ready) => {
			ready.on('mousedown', press)
			ready.on('mousemove', drag)
		},
		(ready) => {
			ready.off('mousedown', press)
			ready.off('mousemove', drag)
			ready.dragPan.enable()
			ready.getCanvas().style.cursor = ''
		},
	)

	// On the window: a drag can end outside the map.
	window.addEventListener('mouseup', release)
	onScopeDispose(() => window.removeEventListener('mouseup', release))

	watch(
		[isReady, () => toValue(isActive)],
		([ready, active]) => {
			if (!ready || !map.value) return
			if (active) map.value.dragPan.disable()
			else map.value.dragPan.enable()
			map.value.getCanvas().style.cursor = active ? 'crosshair' : ''
			if (!active) pressedAt = null
		},
		{ immediate: true },
	)

	return { circle }
}
