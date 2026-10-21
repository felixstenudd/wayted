import type { MapMouseEvent } from 'maplibre-gl'

import { onMap } from '../context'
import type { LonLat } from '../geometry'

export interface ClickedFeature {
	layerId: string
	properties: Record<string, unknown>
}

// A thin line is hard to hit exactly.
const REACH_PX = 4

/** A click on a marker belongs to the marker, though MapLibre reports it as one on the map. */
export const isOnMarker = (event: MapMouseEvent) =>
	event.originalEvent.target instanceof Element &&
	event.originalEvent.target.closest('.maplibregl-marker') !== null

/** Calls back with the topmost feature of the given layers under a click, or null, and where. */
export function useMapClick(
	layerIds: string[],
	onClick: (feature: ClickedFeature | null, at: LonLat) => void,
): void {
	const handle = (event: MapMouseEvent) => {
		if (isOnMarker(event)) return
		const map = event.target
		const { x, y } = event.point
		const [feature] = map.queryRenderedFeatures(
			[
				[x - REACH_PX, y - REACH_PX],
				[x + REACH_PX, y + REACH_PX],
			],
			{ layers: layerIds.filter((id) => map.getLayer(id)) },
		)
		onClick(feature ? { layerId: feature.layer.id, properties: feature.properties } : null, {
			lon: event.lngLat.lng,
			lat: event.lngLat.lat,
		})
	}

	onMap(
		(map) => map.on('click', handle),
		(map) => map.off('click', handle),
	)
}

/** Calls back with where on the map a click landed. */
export function useMapClickAt(onClick: (at: LonLat) => void): void {
	const handle = (event: MapMouseEvent) => {
		if (!isOnMarker(event)) onClick({ lon: event.lngLat.lng, lat: event.lngLat.lat })
	}

	onMap(
		(map) => map.on('click', handle),
		(map) => map.off('click', handle),
	)
}
