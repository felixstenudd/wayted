import { ringBounds, type Bounds } from '@/features/map'

import type { QueuedTiles, QueueStatus } from '../../dev-api/types'
import { tileKey } from '../tileKey'

export interface FailedTile {
	id: string
	key: string
	layer: string
	attempts: number
	lastStatus: string | null
	lastMessage: string | null
	bounds: Bounds
}

export function toMapTiles(queued: QueuedTiles) {
	return {
		type: 'FeatureCollection' as const,
		features: queued.features.map(({ geometry, properties }) => ({
			type: 'Feature' as const,
			geometry,
			properties: {
				key: tileKey(properties),
				layer: properties.layer,
				status: properties.status,
			},
		})),
	}
}

export function countByStatus(queued: QueuedTiles): Record<QueueStatus, number> {
	const counts: Record<QueueStatus, number> = { pending: 0, running: 0, failed: 0 }
	for (const tile of queued.features) counts[tile.properties.status] += 1
	return counts
}

export function failedTiles(queued: QueuedTiles): FailedTile[] {
	return queued.features
		.filter((tile) => tile.properties.status === 'failed')
		.map(({ geometry, properties }) => ({
			id: queueId(properties),
			key: tileKey(properties),
			layer: properties.layer,
			attempts: properties.attempts,
			lastStatus: properties.last_status,
			lastMessage: properties.last_message,
			bounds: ringBounds(geometry.coordinates[0] ?? []),
		}))
}

const queueId = (tile: { layer: string; z: number; x: number; y: number }) =>
	`${tile.layer}/${tileKey(tile)}`

/** True when a tile that was queued is not any more: the worker has finished it. */
export function hasFinishedTiles(before: QueuedTiles, after: QueuedTiles): boolean {
	const stillQueued = new Set(after.features.map((tile) => queueId(tile.properties)))
	return before.features.some((tile) => !stillQueued.has(queueId(tile.properties)))
}
