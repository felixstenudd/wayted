import { describe, expect, it } from 'vitest'

import type { Areas } from '../../dev-api/types'
import {
	areaKey,
	areaLayers,
	byLayer,
	fillOpacity,
	isDotted,
	layerFilter,
	layerToken,
	osmUrl,
	toMapAreas,
} from './areas'

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

const area = (osm_type: 'way' | 'relation', osm_id: number, layer = 'parks') => ({
	type: 'Feature' as const,
	geometry: { type: 'MultiPolygon' as const, coordinates: square },
	properties: { layer, osm_type, osm_id, tags: { leisure: 'park', name: 'Square' } },
})

const areas = (...features: ReturnType<typeof area>[]): Areas => ({
	type: 'FeatureCollection',
	features,
})

describe('toMapAreas', () => {
	it('keeps each outline with its key and layer, as the map flattens nested tags', () => {
		expect(toMapAreas(areas(area('way', 101), area('relation', 30)))).toEqual({
			type: 'FeatureCollection',
			features: [
				{
					type: 'Feature',
					geometry: { type: 'MultiPolygon', coordinates: square },
					properties: { key: 'parks/way/101', layer: 'parks' },
				},
				{
					type: 'Feature',
					geometry: { type: 'MultiPolygon', coordinates: square },
					properties: { key: 'parks/relation/30', layer: 'parks' },
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

describe('areaLayers', () => {
	it('lists the layers in view once each, sorted', () => {
		const inView = areas(
			area('way', 1, 'parks'),
			area('way', 2, 'nature'),
			area('way', 3, 'parks'),
		)
		expect(areaLayers(inView)).toEqual(['nature', 'parks'])
	})
})

describe('layerToken', () => {
	it('gives parks and nature their own colours, and other layers the plain one', () => {
		expect(layerToken('parks')).toBe('--map-park')
		expect(layerToken('nature')).toBe('--map-nature')
		expect(layerToken('water')).toBe('--map-area')
		expect(layerToken('toString')).toBe('--map-area')
	})
})

describe('byLayer', () => {
	it('picks a colour by the layer of each feature', () => {
		expect(byLayer(['nature', 'parks'], (layer) => `colour of ${layer}`, 'grey')).toEqual([
			'match',
			['get', 'layer'],
			'nature',
			'colour of nature',
			'parks',
			'colour of parks',
			'grey',
		])
	})

	it('is the fallback when no layer is in view', () => {
		expect(byLayer([], (layer) => layer, 'grey')).toBe('grey')
	})
})

describe('isDotted', () => {
	it('dots the outline of natural land only, like a vegetation boundary', () => {
		expect(isDotted('nature')).toBe(true)
		expect(isDotted('parks')).toBe(false)
	})
})

describe('fillOpacity', () => {
	it('washes natural land lighter than parks, as it covers far more of the map', () => {
		expect(fillOpacity('nature')).toBeLessThan(fillOpacity('parks'))
	})
})

describe('layerFilter', () => {
	it('keeps only the areas of the given layers', () => {
		expect(layerFilter(['parks'])).toEqual(['in', ['get', 'layer'], ['literal', ['parks']]])
	})
})
