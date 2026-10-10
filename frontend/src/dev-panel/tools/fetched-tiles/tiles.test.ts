import { describe, expect, it } from 'vitest'

import type { FetchedTiles } from '../../dev-api/types'
import { layerCodes, tileFilter, toMapTiles } from './tiles'

const tile = (layer: string, x: number, fetchedAt: string, expiresAt: string) => ({
	type: 'Feature' as const,
	geometry: { type: 'Polygon' as const, coordinates: [[[18, 59]]] },
	properties: { layer, z: 14, x, y: 4821, fetched_at: fetchedAt, expires_at: expiresAt },
})

const tiles: FetchedTiles = {
	type: 'FeatureCollection',
	features: [
		tile('roads', 9013, '2026-10-01T10:00:00Z', '2026-11-01T10:00:00Z'),
		tile('parks', 9013, '2026-10-02T10:00:00Z', '2026-11-02T10:00:00Z'),
		tile('roads', 9014, '2026-10-03T12:00:00+02:00', '2026-10-04T12:00:00+02:00'),
	],
}

describe('toMapTiles', () => {
	it('gives each tile a key and its times as milliseconds', () => {
		const data = toMapTiles(tiles)
		expect(data.features[0]?.properties).toEqual({
			key: '14/9013/4821',
			layer: 'roads',
			fetchedAtMs: Date.parse('2026-10-01T10:00:00Z'),
			expiresAtMs: Date.parse('2026-11-01T10:00:00Z'),
		})
	})

	it('reads a time written with an offset as the same moment', () => {
		const data = toMapTiles(tiles)
		expect(data.features[2]?.properties.fetchedAtMs).toBe(Date.parse('2026-10-03T10:00:00Z'))
	})
})

describe('layerCodes', () => {
	it('lists each layer once, sorted', () => {
		expect(layerCodes(tiles)).toEqual(['parks', 'roads'])
	})
})

describe('tileFilter', () => {
	it('selects the checked layers', () => {
		expect(tileFilter(['roads'])).toEqual(['in', ['get', 'layer'], ['literal', ['roads']]])
	})
})
