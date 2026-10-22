const MAX_CHARS = 60
// Letters that NFD does not split into a base letter and a mark, which would otherwise be lost.
// Applied after lowercasing. The backend's slug uses the same table.
const PLAIN_LETTERS: Record<string, string> = {
	ø: 'o',
	æ: 'ae',
	œ: 'oe',
	ß: 'ss',
	ł: 'l',
	đ: 'd',
	ð: 'd',
	þ: 'th',
	ı: 'i',
}

/**
 * The route name as a file name stem: plain lowercase letters and digits joined
 * by dashes, `route-{id}` when nothing is left. The same rule as `slug` in the
 * backend's `app/logbook/routes/export.py`, so files are named alike whichever
 * side names them.
 */
export function slug(name: string, routeId: number): string {
	const plain = name
		.toLowerCase()
		.replace(/[øæœßłđðþı]/g, (letter) => PLAIN_LETTERS[letter] ?? letter)
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
	const stem = plain
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		// Cut first, then trim again, so a cut that lands on a dash does not end the name with one.
		.slice(0, MAX_CHARS)
		.replace(/-+$/, '')
	return stem || `route-${routeId}`
}
