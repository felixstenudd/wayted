import { distanceM, type LonLat } from '@/features/map'

/** A place a stretch can start or end: the route's start, or where one of its edges ends. */
export interface Junction {
	/** Index in the route's coordinates. */
	point: number
	/** Along the route from its start. */
	distanceM: number
}

/** Junction indexes, from before to after in route order. */
export interface Stretch {
	from: number
	to: number
}

interface RouteEdge {
	length_m: number
	last_point: number
}

// Two junctions this close to a click are equally near; the other end decides.
const TIE_M = 5

export function junctions(edges: readonly RouteEdge[]): Junction[] {
	const all: Junction[] = [{ point: 0, distanceM: 0 }]
	let distance = 0
	for (const edge of edges) {
		distance += edge.length_m
		all.push({ point: edge.last_point, distanceM: distance })
	}
	return all
}

/** The stretch between two junctions in route order, at least one edge long. */
export function orderedStretch(a: number, b: number, junctionCount: number): Stretch {
	if (a !== b) return { from: Math.min(a, b), to: Math.max(a, b) }
	return a < junctionCount - 1 ? { from: a, to: a + 1 } : { from: a - 1, to: a }
}

/** The route edges a stretch covers, as the API counts them. */
export const edgeRange = ({ from, to }: Stretch) => ({ fromSeq: from, toSeq: to - 1 })

const lonLat = (point: readonly number[] | undefined): LonLat => ({
	lon: point?.[0] ?? 0,
	lat: point?.[1] ?? 0,
})

/**
 * The junction closest to a click. Where the route passes one place twice, the pass nearest
 * preferNear (the other end of the stretch) wins.
 */
export function nearestJunction(
	coordinates: readonly (readonly number[])[],
	all: readonly Junction[],
	at: LonLat,
	preferNear?: number,
): { index: number; distanceM: number } | null {
	const measured = all.map((junction, index) => ({
		index,
		distanceM: distanceM(lonLat(coordinates[junction.point]), at),
	}))
	const closest = Math.min(...measured.map((m) => m.distanceM))
	const near = measured.filter((m) => m.distanceM <= closest + TIE_M)
	if (preferNear === undefined) return near[0] ?? null
	return (
		[...near].sort(
			(a, b) => Math.abs(a.index - preferNear) - Math.abs(b.index - preferNear),
		)[0] ?? null
	)
}

export function stretchLine(
	coordinates: readonly (readonly number[])[],
	all: readonly Junction[],
	{ from, to }: Stretch,
): (readonly number[])[] {
	return coordinates.slice(all[from]?.point ?? 0, (all[to]?.point ?? 0) + 1)
}

export const stretchLengthM = (all: readonly Junction[], { from, to }: Stretch) =>
	(all[to]?.distanceM ?? 0) - (all[from]?.distanceM ?? 0)

/** The junctions around the edges a review covers, or null once its route is gone. */
export function reviewStretch(review: {
	from_seq: number | null
	to_seq: number | null
}): Stretch | null {
	if (review.from_seq === null || review.to_seq === null) return null
	return { from: review.from_seq, to: review.to_seq + 1 }
}

/** Whether two stretches share at least one edge. */
export const overlaps = (a: Stretch, b: Stretch) => a.from < b.to && b.from < a.to

/** The point a share of the way along a line, measured on the ground. */
export function pointAlong(
	coordinates: readonly (readonly number[])[],
	share = 0.5,
): LonLat | null {
	const points = coordinates.map(lonLat)
	const lengths = points.slice(1).map((point, i) => distanceM(points[i] ?? point, point))
	let left = lengths.reduce((sum, length) => sum + length, 0) * share
	for (const [i, length] of lengths.entries()) {
		const from = points[i]
		const to = points[i + 1]
		if (from && to && left <= length && length > 0) {
			const t = left / length
			return {
				lon: from.lon + (to.lon - from.lon) * t,
				lat: from.lat + (to.lat - from.lat) * t,
			}
		}
		left -= length
	}
	return points.at(-1) ?? null
}
