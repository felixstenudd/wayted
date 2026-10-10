import { describe, expect, it } from 'vitest'

import type { QueuedTiles, QueueStatus } from '../../dev-api/types'
import { countByStatus, failedTiles, hasFinishedTiles, toMapTiles } from './queue'

const ring = [
	[18, 59],
	[18.1, 59],
	[18.1, 59.1],
	[18, 59.1],
	[18, 59],
]

const tile = (layer: string, x: number, status: QueueStatus, message: string | null = null) => ({
	type: 'Feature' as const,
	geometry: { type: 'Polygon' as const, coordinates: [ring] },
	properties: {
		layer,
		z: 14,
		x,
		y: 4821,
		requested_at: '2026-10-09T10:00:00Z',
		status,
		attempts: status === 'failed' ? 10 : 0,
		next_attempt_at: '2026-10-09T10:00:00Z',
		last_status: message && 'timeout',
		last_message: message,
	},
})

const queued: QueuedTiles = {
	type: 'FeatureCollection',
	features: [
		tile('roads', 1, 'pending'),
		tile('parks', 1, 'pending'),
		tile('roads', 2, 'running'),
		tile('roads', 3, 'failed', 'The source did not answer.'),
	],
}

describe('toMapTiles', () => {
	it('keeps the key, layer and status of each tile', () => {
		const data = toMapTiles(queued)
		expect(data.features.map((f) => f.properties)).toEqual([
			{ key: '14/1/4821', layer: 'roads', status: 'pending' },
			{ key: '14/1/4821', layer: 'parks', status: 'pending' },
			{ key: '14/2/4821', layer: 'roads', status: 'running' },
			{ key: '14/3/4821', layer: 'roads', status: 'failed' },
		])
	})
})

describe('countByStatus', () => {
	it('counts every status, also those with no tile', () => {
		expect(countByStatus(queued)).toEqual({ pending: 2, running: 1, failed: 1 })
		expect(countByStatus({ type: 'FeatureCollection', features: [] })).toEqual({
			pending: 0,
			running: 0,
			failed: 0,
		})
	})
})

describe('failedTiles', () => {
	it('lists the failed tiles with what went wrong and where they are', () => {
		expect(failedTiles(queued)).toEqual([
			{
				id: 'roads/14/3/4821',
				key: '14/3/4821',
				layer: 'roads',
				attempts: 10,
				lastStatus: 'timeout',
				lastMessage: 'The source did not answer.',
				bounds: { west: 18, south: 59, east: 18.1, north: 59.1 },
			},
		])
	})
})

describe('hasFinishedTiles', () => {
	const only = (...tiles: QueuedTiles['features']): QueuedTiles => ({
		type: 'FeatureCollection',
		features: tiles,
	})

	it('is true when a tile has left the queue', () => {
		const after = only(tile('roads', 1, 'pending'), tile('roads', 2, 'running'))
		expect(hasFinishedTiles(queued, after)).toBe(true)
	})

	it('tells the layers of one square apart', () => {
		const before = only(tile('roads', 1, 'running'), tile('parks', 1, 'running'))
		expect(hasFinishedTiles(before, only(tile('parks', 1, 'running')))).toBe(true)
	})

	it('is false when tiles only changed status or were added', () => {
		const after = only(
			...queued.features.map((t) => tile(t.properties.layer, t.properties.x, 'running')),
			tile('roads', 9, 'pending'),
		)
		expect(hasFinishedTiles(queued, after)).toBe(false)
	})
})
