// The panel is in English; en-GB gives 24-hour times.
const dateTime = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

/** A time from the API (ISO text) or from the map (milliseconds), in the reader's time zone. */
export function formatTime(time: string | number): string {
	return dateTime.format(new Date(time))
}

export function formatKm(distanceM: number): string {
	return (distanceM / 1000).toFixed(1)
}

/** "9 parks, 9 roads" from a count per layer. */
export function formatLayerCounts(countByLayer: Record<string, number>): string {
	return Object.entries(countByLayer)
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([layer, count]) => `${count} ${layer}`)
		.join(', ')
}
