import { distanceM, type LonLat } from '@/features/map'

export interface Chevron {
	at: LonLat
	/** Clockwise from north, the way the route runs here. */
	bearingDeg: number
}

const toRadians = (degrees: number) => (degrees * Math.PI) / 180

function bearingDeg(from: LonLat, to: LonLat): number {
	const lat1 = toRadians(from.lat)
	const lat2 = toRadians(to.lat)
	const dLon = toRadians(to.lon - from.lon)
	const y = Math.sin(dLon) * Math.cos(lat2)
	const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon)
	return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
}

/** Marks every spacingM along a line, so a loop reads one way round. */
export function chevronsAlong(
	coordinates: readonly (readonly number[])[],
	spacingM: number,
): Chevron[] {
	const points = coordinates.map(([lon, lat]) => ({ lon: lon ?? 0, lat: lat ?? 0 }))
	const marks: Chevron[] = []
	let next = spacingM
	let walked = 0
	for (let i = 1; i < points.length; i++) {
		const from = points[i - 1]
		const to = points[i]
		if (!from || !to) continue
		const length = distanceM(from, to)
		while (length > 0 && next <= walked + length) {
			const share = (next - walked) / length
			marks.push({
				at: {
					lon: from.lon + (to.lon - from.lon) * share,
					lat: from.lat + (to.lat - from.lat) * share,
				},
				bearingDeg: bearingDeg(from, to),
			})
			next += spacingM
		}
		walked += length
	}
	return marks
}

/**
 * Both ends of a line with the way it runs there, for the ticks that close a bracket. A point
 * repeated at an end is skipped, as it has no direction.
 */
export function lineEnds(coordinates: readonly (readonly number[])[]): Chevron[] {
	const points = coordinates.map(([lon, lat]) => ({ lon: lon ?? 0, lat: lat ?? 0 }))
	const first = points[0]
	const last = points.at(-1)
	if (!first || !last) return []
	const same = (a: LonLat, b: LonLat) => a.lon === b.lon && a.lat === b.lat
	const second = points.find((point) => !same(point, first))
	const beforeLast = [...points].reverse().find((point) => !same(point, last))
	if (!second || !beforeLast) return []
	return [
		{ at: first, bearingDeg: bearingDeg(first, second) },
		{ at: last, bearingDeg: bearingDeg(beforeLast, last) },
	]
}
