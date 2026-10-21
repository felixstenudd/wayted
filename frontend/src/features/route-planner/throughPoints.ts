import { distanceToLineM, type LonLat } from '@/features/map'

import type { ThroughPoint } from './types'

/**
 * The control number of each through point, in the order they were added: its place on the
 * route, from 1, as the route's waypoint order gives it. Undefined while there is no route, which
 * is when the planner has not chosen an order yet.
 */
export function throughPointNumbers(
	waypointOrder: readonly number[] | null,
	count: number,
): (number | undefined)[] {
	return Array.from({ length: count }, (_, index) => {
		const place = waypointOrder?.indexOf(index) ?? -1
		return place === -1 ? undefined : place + 1
	})
}

/** Each point placed as soon as possible and its turn among those, from 1: the order they were added. */
export function soonOrder(
	points: readonly Pick<ThroughPoint, 'id' | 'placement'>[],
): Map<number, number> {
	const soon = points.filter((point) => point.placement.at === 'asap')
	return new Map(soon.map((point, index) => [point.id, index + 1]))
}

// An edited route this much further from a point than the planned one has left it out.
const SKIPPED_BY_M = 30

/**
 * Which points an edit took the route away from. Each is measured against the planned route,
 * which passed it where the nearest road is, not always on the spot.
 */
export function skippedPoints(
	points: readonly LonLat[],
	planned: readonly (readonly number[])[],
	edited: readonly (readonly number[])[],
): boolean[] {
	return points.map(
		(point) => distanceToLineM(point, edited) > distanceToLineM(point, planned) + SKIPPED_BY_M,
	)
}
