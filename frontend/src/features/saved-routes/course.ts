import { distanceM } from '@/features/map'

// A finish this close to the start is the same place: one symbol is enough there.
const SAME_PLACE_M = 30

/** The line of [lon, lat] finishes where it starts, as a loop does. */
export function endsAtStart(line: readonly (readonly number[])[]): boolean {
	const [startLon, startLat] = line[0] ?? []
	const [endLon, endLat] = line.at(-1) ?? []
	if (startLon === undefined || startLat === undefined) return false
	if (endLon === undefined || endLat === undefined) return false
	const start = { lon: startLon, lat: startLat }
	return distanceM(start, { lon: endLon, lat: endLat }) < SAME_PLACE_M
}
