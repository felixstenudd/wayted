// Helpers for a slider from -1 to 1 that snaps to a few values (detents).

const clamp = (value: number) => Math.min(Math.max(value, -1), 1)

export function roundToHundredth(value: number): number {
	return Math.round(value * 100) / 100
}

export function nearestDetent(value: number, detents: readonly number[]): number {
	let nearest = detents[0] ?? 0
	for (const detent of detents) {
		if (Math.abs(detent - value) < Math.abs(nearest - value)) nearest = detent
	}
	return nearest
}

/** The first detent beyond value in a direction, or the end detent when there is none. */
export function nextDetent(value: number, detents: readonly number[], direction: 1 | -1): number {
	const beyond = detents.filter((detent) =>
		direction === 1 ? detent > value + 1e-9 : detent < value - 1e-9,
	)
	if (direction === 1) return beyond[0] ?? detents.at(-1) ?? value
	return beyond.at(-1) ?? detents[0] ?? value
}

/** The value under x on a track from left to left + width. */
export function valueAtX(x: number, left: number, width: number): number {
	return clamp(((x - left) / width) * 2 - 1)
}

export function xOfValue(value: number, left: number, width: number): number {
	return left + ((value + 1) / 2) * width
}
