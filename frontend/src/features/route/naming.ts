export interface NamedRoute {
	shape: 'loop' | 'point_to_point'
	// what was asked for; null for a way to a finish without one
	targetM: number | null
	lengthM: number
}

/**
 * A name to start from when a route is saved, as a message and its values: "8 km loop",
 * "5.2 km route". The one place to grow, such as with a place name from a geocoder.
 */
export function suggestRouteName(route: NamedRoute): {
	key: string
	values: Record<string, string>
} {
	const km = String(Math.round((route.targetM ?? route.lengthM) / 100) / 10)
	return { key: route.shape === 'loop' ? 'route.name.loop' : 'route.name.route', values: { km } }
}
