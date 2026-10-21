import type { GeoJSONSourceSpecification } from 'maplibre-gl'

/** What a GeoJSON source can be given, without the URL form. */
export type MapData = Exclude<GeoJSONSourceSpecification['data'], string>

export interface LonLat {
	lon: number
	lat: number
}

export interface Bounds {
	west: number
	south: number
	east: number
	north: number
}

export interface Circle {
	center: LonLat
	radiusM: number
}

export const EARTH_RADIUS_M = 6_371_008.8
// Web Mercator ends here.
export const MAX_LATITUDE = 85.0511287798

const toRadians = (degrees: number) => (degrees * Math.PI) / 180
const toDegrees = (radians: number) => (radians * 180) / Math.PI
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

/** Great-circle distance in metres. */
export function distanceM(from: LonLat, to: LonLat): number {
	const fromLat = toRadians(from.lat)
	const toLat = toRadians(to.lat)
	const a =
		Math.sin((toLat - fromLat) / 2) ** 2 +
		Math.cos(fromLat) * Math.cos(toLat) * Math.sin(toRadians(to.lon - from.lon) / 2) ** 2
	return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)))
}

/** The outline of a circle on the ground as a closed ring of [lon, lat]. */
export function circleRing(circle: Circle, points = 64): [number, number][] {
	const reach = circle.radiusM / EARTH_RADIUS_M
	const lat = toRadians(circle.center.lat)
	const ring: [number, number][] = []
	for (let i = 0; i < points; i++) {
		const bearing = (2 * Math.PI * i) / points
		const pointLat = Math.asin(
			Math.sin(lat) * Math.cos(reach) + Math.cos(lat) * Math.sin(reach) * Math.cos(bearing),
		)
		const pointLon =
			toRadians(circle.center.lon) +
			Math.atan2(
				Math.sin(bearing) * Math.sin(reach) * Math.cos(lat),
				Math.cos(reach) - Math.sin(lat) * Math.sin(pointLat),
			)
		ring.push([toDegrees(pointLon), toDegrees(pointLat)])
	}
	const first = ring[0]
	if (first) ring.push(first)
	return ring
}

export function circlePolygon(circle: Circle): MapData {
	return {
		type: 'Feature',
		properties: {},
		geometry: { type: 'Polygon', coordinates: [circleRing(circle)] },
	}
}

/** Bounds a server accepts: inside the world, never across the antimeridian. */
export function clampBounds(bounds: Bounds): Bounds {
	return {
		west: clamp(bounds.west, -180, 180),
		south: clamp(bounds.south, -MAX_LATITUDE, MAX_LATITUDE),
		east: clamp(bounds.east, -180, 180),
		north: clamp(bounds.north, -MAX_LATITUDE, MAX_LATITUDE),
	}
}

export function boundsPolygon({ west, south, east, north }: Bounds): MapData {
	return {
		type: 'Feature',
		properties: {},
		geometry: {
			type: 'Polygon',
			coordinates: [
				[
					[west, south],
					[east, south],
					[east, north],
					[west, north],
					[west, south],
				],
			],
		},
	}
}

/** The bounds of a ring of [lon, lat]. */
export function ringBounds(ring: readonly (readonly number[])[]): Bounds {
	const lons = ring.map((point) => point[0] ?? 0)
	const lats = ring.map((point) => point[1] ?? 0)
	return {
		west: Math.min(...lons),
		south: Math.min(...lats),
		east: Math.max(...lons),
		north: Math.max(...lats),
	}
}

/** Shortest distance in metres from point to a line of [lon, lat]; for lines a few km long. */
export function distanceToLineM(point: LonLat, line: readonly (readonly number[])[]): number {
	// Metres east and north of point, flat at this scale.
	const metresPerDegree = (Math.PI * EARTH_RADIUS_M) / 180
	const across = metresPerDegree * Math.cos(toRadians(point.lat))
	const toXY = (position: readonly number[]): [number, number] => [
		((position[0] ?? 0) - point.lon) * across,
		((position[1] ?? 0) - point.lat) * metresPerDegree,
	]
	const points = line.map(toXY)
	let nearestM = points[0] ? Math.hypot(...points[0]) : Infinity
	points.slice(1).forEach(([bx, by], index) => {
		const [ax, ay] = points[index] ?? [bx, by]
		const lengthSq = (bx - ax) ** 2 + (by - ay) ** 2
		const share =
			lengthSq === 0 ? 0 : clamp(-(ax * (bx - ax) + ay * (by - ay)) / lengthSq, 0, 1)
		nearestM = Math.min(nearestM, Math.hypot(ax + share * (bx - ax), ay + share * (by - ay)))
	})
	return nearestM
}

export const EMPTY: MapData = { type: 'FeatureCollection', features: [] }
