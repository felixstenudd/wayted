import type { ExpressionSpecification, FilterSpecification } from 'maplibre-gl'

import type { FetchedTile, FetchedTiles } from '../../dev-api/types'
import { tileKey } from '../tileKey'

export interface TimeRange {
	startMs: number
	endMs: number
}

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

/** From the oldest fetch to now; null when nothing is fetched. */
export function timeRange(tiles: FetchedTiles, nowMs: number): TimeRange | null {
	const fetched = tiles.features.map((tile) => Date.parse(tile.properties.fetched_at))
	if (fetched.length === 0) return null
	return { startMs: Math.min(...fetched, nowMs), endMs: nowMs }
}

/** The next time of a playback in steps, or null when it has reached the end. */
export function advance(currentMs: number, range: TimeRange, steps: number): number | null {
	const nextMs = currentMs + (range.endMs - range.startMs) / steps
	return nextMs >= range.endMs ? null : nextMs
}

export function countExpired(tiles: FetchedTiles, nowMs: number): number {
	return tiles.features.filter((tile) => Date.parse(tile.properties.expires_at) <= nowMs).length
}

/** Every layer's tile at one square, by layer. */
export function tilesAt(tiles: FetchedTiles, key: string): FetchedTile[] {
	return tiles.features
		.map((tile) => tile.properties)
		.filter((tile) => tileKey(tile) === key)
		.sort((a, b) => a.layer.localeCompare(b.layer))
}

/**
 * Tiles of the checked layers fetched until a time (null: until now, whatever the server's
 * clock says): all of them, the valid or the expired.
 */
export function tileFilter(
	layers: string[],
	untilMs: number | null,
	nowMs: number,
	expiry: 'any' | 'valid' | 'expired',
): FilterSpecification {
	const shown: ExpressionSpecification[] = [['in', ['get', 'layer'], ['literal', layers]]]
	if (untilMs !== null) shown.push(['<=', ['get', 'fetchedAtMs'], untilMs])
	if (expiry === 'valid') shown.push(['>', ['get', 'expiresAtMs'], nowMs])
	if (expiry === 'expired') shown.push(['<=', ['get', 'expiresAtMs'], nowMs])
	return ['all', ...shown]
}
