import type { FilterSpecification } from 'maplibre-gl'

import type { FetchedTiles } from '../../dev-api/types'
import { tileKey } from '../tileKey'

/** Flat features for the map: times as numbers, so filters compare numbers. */
export function toMapTiles(tiles: FetchedTiles) {
	return {
		type: 'FeatureCollection' as const,
		features: tiles.features.map(({ geometry, properties }) => ({
			type: 'Feature' as const,
			geometry,
			properties: {
				key: tileKey(properties),
				layer: properties.layer,
				fetchedAtMs: Date.parse(properties.fetched_at),
				expiresAtMs: Date.parse(properties.expires_at),
			},
		})),
	}
}

export function layerCodes(tiles: FetchedTiles): string[] {
	return [...new Set(tiles.features.map((tile) => tile.properties.layer))].sort()
}

/** Tiles of the checked layers. */
export function tileFilter(layers: string[]): FilterSpecification {
	return ['in', ['get', 'layer'], ['literal', layers]]
}
