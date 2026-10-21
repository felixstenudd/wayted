export interface SilhouetteBox {
	width: number
	height: number
	padding: number
}

export interface Silhouette {
	/** SVG path data in the box's coordinates. */
	path: string
	start: { x: number; y: number }
}

const round = (value: number) => Math.round(value * 10) / 10

/**
 * A route's line fitted into a box, north up, keeping its shape: a degree of longitude is
 * shortened by the latitude so a square block stays square.
 */
export function silhouette(
	coordinates: readonly (readonly number[])[],
	{ width, height, padding }: SilhouetteBox,
): Silhouette | null {
	const lonLats = coordinates.filter(([lon, lat]) => lon !== undefined && lat !== undefined)
	if (lonLats.length === 0) return null

	const meanLat = lonLats.reduce((sum, [, lat]) => sum + (lat ?? 0), 0) / lonLats.length
	const shrink = Math.cos((meanLat * Math.PI) / 180)
	const points = lonLats.map(([lon, lat]) => ({ x: (lon ?? 0) * shrink, y: -(lat ?? 0) }))

	const xs = points.map((p) => p.x)
	const ys = points.map((p) => p.y)
	const [minX, maxX, minY, maxY] = [
		Math.min(...xs),
		Math.max(...xs),
		Math.min(...ys),
		Math.max(...ys),
	]
	const spanX = maxX - minX
	const spanY = maxY - minY
	const scales = [
		spanX > 0 ? (width - 2 * padding) / spanX : Infinity,
		spanY > 0 ? (height - 2 * padding) / spanY : Infinity,
	]
	const scale = Math.min(...scales)
	const fit = Number.isFinite(scale) ? scale : 0
	const offsetX = (width - spanX * fit) / 2
	const offsetY = (height - spanY * fit) / 2

	const placed = points.map((p) => ({
		x: round(offsetX + (p.x - minX) * fit),
		y: round(offsetY + (p.y - minY) * fit),
	}))
	const path = placed.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x} ${p.y}`).join('')
	return { path, start: placed[0] ?? { x: width / 2, y: height / 2 } }
}
