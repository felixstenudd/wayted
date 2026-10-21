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
