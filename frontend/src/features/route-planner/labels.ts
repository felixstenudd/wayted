type Position = [number, number]

// Enough points to find a clear spot on a long route without comparing every pair.
const SAMPLES = 200

function sample(line: readonly Position[]): Position[] {
	if (line.length <= SAMPLES) return [...line]
	const step = line.length / SAMPLES
	return Array.from({ length: SAMPLES }, (_, i) => line[Math.floor(i * step)] as Position)
}

// Squared distance with longitude shrunk to its length at this latitude, close enough for
// ranking points across a city.
function distance2([aLon, aLat]: Position, [bLon, bLat]: Position): number {
	const dx = (aLon - bLon) * Math.cos((aLat * Math.PI) / 180)
	const dy = aLat - bLat
	return dx * dx + dy * dy
}

/**
 * Where to put each route's label: the point on it farthest from every other route, so labels
 * sit where the routes go their own ways. A lone route gets the point halfway along its points.
 */
export function labelPoints(lines: readonly (readonly Position[])[]): (Position | null)[] {
	const samples = lines.map(sample)
	return samples.map((own, index) => {
		const others = samples.filter((_, other) => other !== index).flat()
		if (others.length === 0) return own[Math.floor(own.length / 2)] ?? null
		let best: Position | null = null
		let bestDistance = -1
		for (const point of own) {
			const nearest = Math.min(...others.map((other) => distance2(point, other)))
			if (nearest > bestDistance) {
				best = point
				bestDistance = nearest
			}
		}
		return best
	})
}
