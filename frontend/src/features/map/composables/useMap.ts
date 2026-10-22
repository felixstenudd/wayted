import {
	Map as MapLibreMap,
	NavigationControl,
	ScaleControl,
	type ControlPosition,
	type StyleSpecification,
} from 'maplibre-gl'
import { onBeforeUnmount, onMounted, type Ref } from 'vue'

import { useMapContext } from '../context'
import type { LonLat } from '../geometry'
import '../maplibre'

// OpenStreetMap's attribution guidelines let shown credits collapse after five seconds.
const CREDITS_SHOWN_MS = 5000

// Loads like any style, so overlays can be drawn without a base map.
const EMPTY_STYLE: StyleSpecification = { version: 8, sources: {}, layers: [] }

export interface MapViewOptions {
	center: LonLat
	zoom: number
	// keeps the position in the URL, so a reload shows the same place
	keepViewInUrl?: boolean
	// undefined is allowed so MapView can pass its optional prop on as it is
	zoomButtonsPosition?: ControlPosition | undefined
}

/** Owns the MapLibre instance of one MapView. */
export function useMap(
	container: Readonly<Ref<HTMLElement | null>>,
	options: MapViewOptions,
): void {
	const context = useMapContext()
	let collapseCredits: ReturnType<typeof setTimeout> | undefined

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
			// North stays up: there is no compass to turn the map back.
			dragRotate: false,
			touchPitch: false,
		})
		map.keyboard.disableRotation()
		map.touchZoomRotate.disableRotation()
		map.addControl(
			new NavigationControl({ showCompass: false }),
			options.zoomButtonsPosition ?? 'top-right',
		)
		map.addControl(new ScaleControl(), 'bottom-right')

		// The style, not the tiles: the tools should not wait for a slow tile server.
		// MapLibre only folds narrow-map credits into their (i) button on a drag; this
		// does the same when nobody drags. The class is what its own drag handler removes.
		map.once('load', () => {
			collapseCredits = setTimeout(() => {
				container.value
					?.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact-show')
					?.classList.remove('maplibregl-compact-show')
			}, CREDITS_SHOWN_MS)
		})

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
		clearTimeout(collapseCredits)
		context.isReady.value = false
		context.map.value?.remove()
		context.map.value = null
	})
}
