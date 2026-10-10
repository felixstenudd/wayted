import {
	Map as MapLibreMap,
	NavigationControl,
	ScaleControl,
	setWorkerUrl,
	type StyleSpecification,
} from 'maplibre-gl'
// Bundled by Vite: MapLibre cannot find its own worker file once it is in a bundle.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { onBeforeUnmount, onMounted, type Ref } from 'vue'

import { useMapContext } from '../context'
import type { LonLat } from '../geometry'

setWorkerUrl(workerUrl)

// Loads like any style, so overlays can be drawn without a base map.
const EMPTY_STYLE: StyleSpecification = { version: 8, sources: {}, layers: [] }

export interface MapViewOptions {
	center: LonLat
	zoom: number
	// keeps the position in the URL, so a reload shows the same place
	keepViewInUrl?: boolean
}

/** Owns the MapLibre instance of one MapView. */
export function useMap(
	container: Readonly<Ref<HTMLElement | null>>,
	options: MapViewOptions,
): void {
	const context = useMapContext()

	onMounted(() => {
		if (!container.value) return
		const styleUrl = import.meta.env.VITE_MAP_STYLE_URL
		if (!styleUrl) context.hasBaseMapFailed.value = true
		const map = new MapLibreMap({
			container: container.value,
			style: styleUrl || EMPTY_STYLE,
			center: [options.center.lon, options.center.lat],
			zoom: options.zoom,
			hash: options.keepViewInUrl ?? false,
			// One world, so a view never spans the antimeridian twice.
			renderWorldCopies: false,
		})
		map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
		map.addControl(new ScaleControl(), 'bottom-right')

		// The style, not the tiles: the tools should not wait for a slow tile server.
		map.on('style.load', () => {
			context.isReady.value = true
		})
		map.on('error', (event) => {
			const hasStyleFailed = !context.isReady.value && !context.hasBaseMapFailed.value
			if (hasStyleFailed) {
				context.hasBaseMapFailed.value = true
				map.setStyle(EMPTY_STYLE)
				return
			}
			// MapLibre stays silent once someone listens for its errors.
			console.error(event.error)
		})
		context.map.value = map
	})

	onBeforeUnmount(() => {
		context.isReady.value = false
		context.map.value?.remove()
		context.map.value = null
	})
}
