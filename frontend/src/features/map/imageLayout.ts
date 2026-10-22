import { MAX_LATITUDE, type Bounds } from './geometry'

/** An image's size in CSS pixels. */
export interface ImageFrame {
	width: number
	height: number
}

export interface ImagePadding {
	top: number
	bottom: number
	left: number
	right: number
}

export interface Rect {
	x: number
	y: number
	width: number
	height: number
}

// The sizes link previews and photo feeds show uncropped.
export const LANDSCAPE: ImageFrame = { width: 1200, height: 630 }
export const PORTRAIT: ImageFrame = { width: 1080, height: 1350 }
// Kept clear on each side, as a share of that side's direction.
export const PADDING_SHARE = 0.08

export const ATTRIBUTION = '© OpenFreeMap © OpenStreetMap contributors'
export const ATTRIBUTION_FONT_PX = 12
const ATTRIBUTION_PADDING_X = 6
const ATTRIBUTION_PADDING_Y = 4

const toRadians = (degrees: number) => (degrees * Math.PI) / 180
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

// Web Mercator northing, so a span compares with the eastings the map shows beside it.
function mercatorY(lat: number): number {
	const phi = toRadians(clamp(lat, -MAX_LATITUDE, MAX_LATITUDE))
	return Math.log(Math.tan(Math.PI / 4 + phi / 2))
}

/**
 * Landscape or portrait, whichever the bounds fill more of once fitted inside the padding.
 * The bounds are compared as the map draws them, so a route far north is taller than its degrees.
 */
export function chooseFrame(bounds: Bounds): ImageFrame {
	const width = toRadians(bounds.east - bounds.west)
	const height = mercatorY(bounds.north) - mercatorY(bounds.south)
	// A single point or a line straight east.
	if (height <= 0) return LANDSCAPE
	// The padding is the same share both ways, so a frame's inside keeps its aspect. Both fill
	// the same share where the route's aspect is their geometric mean.
	const threshold = Math.sqrt(
		(LANDSCAPE.width / LANDSCAPE.height) * (PORTRAIT.width / PORTRAIT.height),
	)
	return width / height >= threshold ? LANDSCAPE : PORTRAIT
}

/** The space kept clear around the route, in CSS pixels. */
export function imagePadding(frame: ImageFrame): ImagePadding {
	const across = Math.round(frame.width * PADDING_SHARE)
	const along = Math.round(frame.height * PADDING_SHARE)
	return { top: along, bottom: along, left: across, right: across }
}

/** The credits strip in the bottom-right corner, sized to its text, as MapLibre places its own. */
export function attributionStrip(frame: ImageFrame, textWidth: number): Rect {
	const width = Math.ceil(textWidth) + 2 * ATTRIBUTION_PADDING_X
	const height = ATTRIBUTION_FONT_PX + 2 * ATTRIBUTION_PADDING_Y
	return { x: frame.width - width, y: frame.height - height, width, height }
}
