import type { ExpressionSpecification, FilterSpecification } from 'maplibre-gl'

import type { Area } from '../../dev-api/types'

type Element = Pick<Area, 'osm_type' | 'osm_id'>
// Areas or lines: both come with the same properties.
type Features<Geometry> = { features: { geometry: Geometry; properties: Area }[] }

const LAYER_TOKENS: Record<string, string> = {
	parks: '--map-park',
	nature: '--map-nature',
	water: '--map-water',
	water_lines: '--map-water',
}
// Drawn like an orienteering map's vegetation boundary; parks keep a built, solid edge.
const DOTTED_LAYERS = new Set(['nature'])

export const areaKey = (area: Pick<Area, 'layer'> & Element) =>
	`${area.layer}/${area.osm_type}/${area.osm_id}`

/** Flat features for the map: the key and layer only, as the map would flatten the nested tags. */
export function toMapAreas<Geometry>(areas: Features<Geometry>) {
	return {
		type: 'FeatureCollection' as const,
		features: areas.features.map(({ geometry, properties }) => ({
			type: 'Feature' as const,
			geometry,
			properties: { key: areaKey(properties), layer: properties.layer },
		})),
	}
}

export function areaLayers<Geometry>(areas: Features<Geometry>): string[] {
	return [...new Set(areas.features.map((area) => area.properties.layer))].sort()
}

/** The colour token of a layer; a layer without its own is drawn in the plain area colour. */
export const layerToken = (layer: string) =>
	(Object.hasOwn(LAYER_TOKENS, layer) ? LAYER_TOKENS[layer] : undefined) ?? '--map-area'

export const isDotted = (layer: string) => DOTTED_LAYERS.has(layer)

export const layerFilter = (layers: string[]): FilterSpecification => [
	'in',
	['get', 'layer'],
	['literal', layers],
]

// Natural land covers far more of the map than parks, so its wash is lighter.
const FILL_OPACITIES: Record<string, number> = { parks: 0.25, nature: 0.12 }

export const fillOpacity = (layer: string) =>
	(Object.hasOwn(FILL_OPACITIES, layer) ? FILL_OPACITIES[layer] : undefined) ?? 0.2

/** A paint value that differs by each feature's layer. */
export function byLayer<Value extends string | number>(
	layers: string[],
	valueOf: (layer: string) => Value,
	fallback: Value,
): ExpressionSpecification | Value {
	const [first, ...rest] = layers
	if (first === undefined) return fallback
	return [
		'match',
		['get', 'layer'],
		first,
		valueOf(first),
		...rest.flatMap((layer) => [layer, valueOf(layer)]),
		fallback,
	]
}

export const osmUrl = (area: Element) =>
	`https://www.openstreetmap.org/${area.osm_type}/${area.osm_id}`
