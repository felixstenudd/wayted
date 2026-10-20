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

/**
 * Labels joined as one sentence: "Nice greenery and lots to see". Each label is written to stand
 * alone with a capital, so the ones after the first lose it.
 */
export function joinLabels(labels: readonly string[], locale: string): string {
	const inSentence = labels.map((label, i) =>
		i === 0 ? label : label.charAt(0).toLocaleLowerCase(locale) + label.slice(1),
	)
	return new Intl.ListFormat(locale, { type: 'conjunction' }).format(inSentence)
}
