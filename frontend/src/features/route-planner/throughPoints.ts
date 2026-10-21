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
