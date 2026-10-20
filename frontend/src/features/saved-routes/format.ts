/** The day a route was saved, with the year only when it is not this year's. */
export function formatSavedOn(savedAt: string, now: Date, locale: string): string {
	const date = new Date(savedAt)
	return new Intl.DateTimeFormat(locale, {
		day: 'numeric',
		month: 'short',
		...(date.getFullYear() !== now.getFullYear() && { year: 'numeric' }),
	}).format(date)
}

/** Kilometres with one decimal, so routes in a list line up. */
export function formatDistanceKm(distanceM: number, locale: string): string {
	return new Intl.NumberFormat(locale, {
		minimumFractionDigits: 1,
		maximumFractionDigits: 1,
	}).format(distanceM / 1000)
}
