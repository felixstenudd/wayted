import { describe, expect, it } from 'vitest'

import type { FetchedTiles } from '../../dev-api/types'
import {
	advance,
	countExpired,
	layerCodes,
	tileFilter,
	tilesAt,
	timeRange,
	toMapTiles,
} from './tiles'

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
const now = Date.parse('2026-10-09T00:00:00Z')

describe('toMapTiles', () => {
	it('gives each tile a key and its times as milliseconds', () => {
		const data = toMapTiles(tiles)
		if (data.type !== 'FeatureCollection') throw new Error()
		expect(data.features[0]?.properties).toEqual({
			key: '14/9013/4821',
			layer: 'roads',
			fetchedAtMs: Date.parse('2026-10-01T10:00:00Z'),
			expiresAtMs: Date.parse('2026-11-01T10:00:00Z'),
		})
	})

	it('reads a time written with an offset as the same moment', () => {
		const data = toMapTiles(tiles)
		if (data.type !== 'FeatureCollection') throw new Error()
		expect(data.features[2]?.properties.fetchedAtMs).toBe(Date.parse('2026-10-03T10:00:00Z'))
	})
})

describe('layerCodes', () => {
	it('lists each layer once, sorted', () => {
		expect(layerCodes(tiles)).toEqual(['parks', 'roads'])
	})
})

describe('timeRange', () => {
	it('runs from the oldest fetch to now', () => {
		expect(timeRange(tiles, now)).toEqual({
			startMs: Date.parse('2026-10-01T10:00:00Z'),
			endMs: now,
		})
	})

	it('is null when nothing is fetched', () => {
		expect(timeRange({ type: 'FeatureCollection', features: [] }, now)).toBeNull()
	})

	it('never starts after it ends when a clock is ahead', () => {
		const early = Date.parse('2026-09-01T00:00:00Z')
		expect(timeRange(tiles, early)).toEqual({ startMs: early, endMs: early })
	})
})

describe('advance', () => {
	const range = { startMs: 0, endMs: 1000 }

	it('moves one step forward', () => {
		expect(advance(0, range, 10)).toBe(100)
	})

	it('ends when the next step reaches the end', () => {
		expect(advance(900, range, 10)).toBeNull()
		expect(advance(5, { startMs: 5, endMs: 5 }, 10)).toBeNull()
	})
})

describe('countExpired', () => {
	it('counts tiles whose expiry has passed', () => {
		expect(countExpired(tiles, now)).toBe(1)
	})
})

describe('tilesAt', () => {
	it('returns every layer of one square, by layer', () => {
		expect(tilesAt(tiles, '14/9013/4821').map((t) => t.layer)).toEqual(['parks', 'roads'])
		expect(tilesAt(tiles, '14/1/1')).toEqual([])
	})
})

describe('tileFilter', () => {
	const shown = [
		['in', ['get', 'layer'], ['literal', ['roads']]],
		['<=', ['get', 'fetchedAtMs'], 500],
	]

	it('selects by layer and fetch time', () => {
		expect(tileFilter(['roads'], 500, 900, 'any')).toEqual(['all', ...shown])
	})

	it('can keep only the valid or only the expired tiles', () => {
		expect(tileFilter(['roads'], 500, 900, 'valid')).toEqual([
			'all',
			...shown,
			['>', ['get', 'expiresAtMs'], 900],
		])
		expect(tileFilter(['roads'], 500, 900, 'expired')).toEqual([
			'all',
			...shown,
			['<=', ['get', 'expiresAtMs'], 900],
		])
	})
})
