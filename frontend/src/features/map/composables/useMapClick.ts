import type { MapMouseEvent } from 'maplibre-gl'

import { onMap } from '../context'

export interface ClickedFeature {
	layerId: string
	properties: Record<string, unknown>
}

// A thin line is hard to hit exactly.
const REACH_PX = 4

/** Calls back with the topmost feature of the given layers under a click, or null. */
export function useMapClick(
	layerIds: string[],
	onClick: (feature: ClickedFeature | null) => void,
): void {
	const handle = (event: MapMouseEvent) => {
		const map = event.target
		const { x, y } = event.point
		const [feature] = map.queryRenderedFeatures(
			[
				[x - REACH_PX, y - REACH_PX],
				[x + REACH_PX, y + REACH_PX],
			],
			{ layers: layerIds.filter((id) => map.getLayer(id)) },
		)
		onClick(feature ? { layerId: feature.layer.id, properties: feature.properties } : null)
	}

	onMap(
		(map) => map.on('click', handle),
		(map) => map.off('click', handle),
	)
}
