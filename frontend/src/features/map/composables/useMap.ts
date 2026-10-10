import { Map as MapLibreMap, NavigationControl, ScaleControl, setWorkerUrl } from 'maplibre-gl'
// Bundled by Vite: MapLibre cannot find its own worker file once it is in a bundle.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { onBeforeUnmount, onMounted, type Ref } from 'vue'

import { useMapContext } from '../context'
import type { LonLat } from '../geometry'

setWorkerUrl(workerUrl)

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
		const map = new MapLibreMap({
			container: container.value,
			style: import.meta.env.VITE_MAP_STYLE_URL,
			center: [options.center.lon, options.center.lat],
			zoom: options.zoom,
			hash: options.keepViewInUrl ?? false,
			// One world, so a view never spans the antimeridian twice.
			renderWorldCopies: false,
		})
		map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
		map.addControl(new ScaleControl(), 'bottom-right')

		map.once('load', () => {
			context.isReady.value = true
		})
		map.on('error', () => {
			if (context.isReady.value || context.hasBaseMapFailed.value) return
			context.hasBaseMapFailed.value = true
			// An empty style still loads, so overlays can be drawn without the base map.
			map.setStyle({ version: 8, sources: {}, layers: [] })
		})
		context.map.value = map
	})

	onBeforeUnmount(() => {
		context.isReady.value = false
		context.map.value?.remove()
		context.map.value = null
	})
}
