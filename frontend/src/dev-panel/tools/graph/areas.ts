import type { Area, Areas } from '../../dev-api/types'

type Element = Pick<Area, 'osm_type' | 'osm_id'>

export const areaKey = (area: Pick<Area, 'layer'> & Element) =>
	`${area.layer}/${area.osm_type}/${area.osm_id}`

/** Flat features for the map: the key only, as the map would flatten the nested tags. */
export function toMapAreas(areas: Areas) {
	return {
		type: 'FeatureCollection' as const,
		features: areas.features.map(({ geometry, properties }) => ({
			type: 'Feature' as const,
			geometry,
			properties: { key: areaKey(properties) },
		})),
	}
}

export const osmUrl = (area: Element) =>
	`https://www.openstreetmap.org/${area.osm_type}/${area.osm_id}`
