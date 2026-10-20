import { readonly, ref, type Ref } from 'vue'

import { onMap, useMapContext } from '../context'
import { clampBounds, type Bounds, type LonLat } from '../geometry'

const PADDING_PX = 48
// Close enough to see which street a point is on.
const POINT_ZOOM = 15

/** How far, in px, something drawn over the map covers it from each edge. */
export interface MapCover {
	top?: number
	right?: number
	bottom?: number
	left?: number
}

/** The bounds of what the map shows, and a way to move it. */
export function useMapView(): {
	bounds: Readonly<Ref<Bounds | null>>
	showBounds: (bounds: Bounds, cover?: MapCover) => void
	center: () => LonLat | null
	showPoint: (at: LonLat) => void
} {
	const { map } = useMapContext()
	const bounds = ref<Bounds | null>(null)

	const read = () => {
		const view = map.value?.getBounds()
		if (!view) return
		bounds.value = clampBounds({
			west: view.getWest(),
			south: view.getSouth(),
			east: view.getEast(),
			north: view.getNorth(),
		})
	}

	onMap(
		(ready) => {
			read()
			ready.on('moveend', read)
		},
		(ready) => ready.off('moveend', read),
	)

	/** Fits the map to bounds, keeping them clear of what covers the map. */
	const showBounds = ({ west, south, east, north }: Bounds, cover: MapCover = {}) => {
		map.value?.fitBounds(
			[
				[west, south],
				[east, north],
			],
			{
				padding: {
					top: PADDING_PX + (cover.top ?? 0),
					right: PADDING_PX + (cover.right ?? 0),
					bottom: PADDING_PX + (cover.bottom ?? 0),
					left: PADDING_PX + (cover.left ?? 0),
				},
			},
		)
	}

	const center = (): LonLat | null => {
		const at = map.value?.getCenter()
		return at ? { lon: at.lng, lat: at.lat } : null
	}

	/** Moves the map to a point, zooming in when it is further out than street level. */
	const showPoint = ({ lon, lat }: LonLat) => {
		const zoom = Math.max(map.value?.getZoom() ?? POINT_ZOOM, POINT_ZOOM)
		map.value?.easeTo({ center: [lon, lat], zoom })
	}

	return { bounds: readonly(bounds), showBounds, center, showPoint }
}
