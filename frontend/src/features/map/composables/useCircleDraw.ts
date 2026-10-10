import type { MapMouseEvent } from 'maplibre-gl'
import { onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import { onMap, useMapContext } from '../context'
import { distanceM, type Circle } from '../geometry'

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
	let isPressing = false

	const press = (event: MapMouseEvent) => {
		if (!toValue(isActive)) return
		isPressing = true
		circle.value = { center: { lon: event.lngLat.lng, lat: event.lngLat.lat }, radiusM: 0 }
	}
	const drag = (event: MapMouseEvent) => {
		if (!isPressing || !circle.value) return
		const to = { lon: event.lngLat.lng, lat: event.lngLat.lat }
		const radiusM = Math.min(distanceM(circle.value.center, to), maxRadiusM)
		circle.value = { center: circle.value.center, radiusM }
	}
	const release = () => {
		if (!isPressing) return
		isPressing = false
		if (circle.value?.radiusM === 0) circle.value = null
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
			if (!active) isPressing = false
		},
		{ immediate: true },
	)

	return { circle }
}
