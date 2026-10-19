import { describe, expect, it } from 'vitest'

import type { Areas } from '../../dev-api/types'
import { areaKey, osmUrl, toMapAreas } from './areas'

const square = [
	[
		[
			[18, 59],
			[18.1, 59],
			[18.1, 59.1],
			[18, 59],
		],
	],
]

const area = (osm_type: 'way' | 'relation', osm_id: number) => ({
	type: 'Feature' as const,
	geometry: { type: 'MultiPolygon' as const, coordinates: square },
	properties: { layer: 'parks', osm_type, osm_id, tags: { leisure: 'park', name: 'Square' } },
})

const areas = (...features: ReturnType<typeof area>[]): Areas => ({
	type: 'FeatureCollection',
	features,
})

describe('toMapAreas', () => {
	it('keeps each outline with only its key, as the map flattens nested tags', () => {
		expect(toMapAreas(areas(area('way', 101), area('relation', 30)))).toEqual({
			type: 'FeatureCollection',
			features: [
				{
					type: 'Feature',
					geometry: { type: 'MultiPolygon', coordinates: square },
					properties: { key: 'parks/way/101' },
				},
				{
					type: 'Feature',
					geometry: { type: 'MultiPolygon', coordinates: square },
					properties: { key: 'parks/relation/30' },
				},
			],
		})
	})
})

describe('areaKey', () => {
	it('tells the same element in two layers apart', () => {
		const park = area('way', 101).properties
		expect(areaKey(park)).not.toBe(areaKey({ ...park, layer: 'forests' }))
	})
})

describe('osmUrl', () => {
	it('links to the element on openstreetmap.org', () => {
		expect(osmUrl(area('relation', 30).properties)).toBe(
			'https://www.openstreetmap.org/relation/30',
		)
	})
})
