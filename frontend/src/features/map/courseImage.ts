import { Map as MapLibreMap } from 'maplibre-gl'

import { tokenColor } from './colors'
import { ringBounds } from './geometry'
import {
	ATTRIBUTION,
	ATTRIBUTION_FONT_PX,
	attributionStrip,
	chooseFrame,
	imagePadding,
	type ImageFrame,
} from './imageLayout'
import './maplibre'

const PIXEL_RATIO = 2
const IDLE_TIMEOUT_MS = 15_000
// A little larger than on screen: the image is seen whole, often small.
const SYMBOL_PX = 32
// CourseSymbol's drawing, in its 28-unit view box.
const SYMBOL_VIEW = 28
const SYMBOL_STROKE = 2.5
const START_PATH = 'M14 3.5 25 23.5H3Z'
// The start, smaller, inside the finish's outer circle.
const LOOP_START_PATH = 'M14 6.5 21 19H7Z'

type SymbolKind = 'start' | 'finish' | 'loop'

export interface CourseImageOptions {
	/** The finish is where the start is, so one symbol stands for both. */
	isLoop: boolean
}

/**
 * Draws a course line of [lon, lat] on the base map as a PNG, with its start and finish symbols
 * and the map's credits. Rejects, and makes no image, when there is no base map style or the map
 * fails or is not fully drawn within 15 s.
 */
export async function renderCourseImage(
	line: readonly (readonly number[])[],
	{ isLoop }: CourseImageOptions,
): Promise<Blob> {
	const styleUrl = import.meta.env.VITE_MAP_STYLE_URL
	if (!styleUrl) throw new Error('No base map style is set.')
	if (line.length < 2) throw new Error('A course needs at least two points.')

	const bounds = ringBounds(line)
	const frame = chooseFrame(bounds)
	const container = document.createElement('div')
	// Laid out at full size, so MapLibre draws it, but out of sight and out of reach.
	Object.assign(container.style, {
		position: 'fixed',
		top: '0',
		left: '-100000px',
		width: `${frame.width}px`,
		height: `${frame.height}px`,
		visibility: 'hidden',
		pointerEvents: 'none',
	})
	container.setAttribute('aria-hidden', 'true')
	document.body.append(container)

	let map: MapLibreMap | null = null
	try {
		map = new MapLibreMap({
			container,
			style: styleUrl,
			bounds: [bounds.west, bounds.south, bounds.east, bounds.north],
			fitBoundsOptions: { padding: imagePadding(frame) },
			pixelRatio: PIXEL_RATIO,
			// Kept after each frame, so the canvas can be read once the map is idle.
			canvasContextAttributes: { preserveDrawingBuffer: true },
			interactive: false,
			attributionControl: false,
			renderWorldCopies: false,
			// Labels appear at once rather than fading in after the map reports idle.
			fadeDuration: 0,
		})
		const drawn = map
		await whenDrawn(drawn, () => addCourse(drawn, line, isLoop))
		return await compose(drawn.getCanvas(), frame)
	} finally {
		map?.remove()
		container.remove()
	}
}

// Resolves once the style, every tile and the course are drawn; any error before that rejects.
function whenDrawn(map: MapLibreMap, prepare: () => void): Promise<void> {
	return new Promise((resolve, reject) => {
		const timer = setTimeout(
			() => reject(new Error('The map was not drawn in time.')),
			IDLE_TIMEOUT_MS,
		)
		const fail = (error: unknown) => {
			clearTimeout(timer)
			reject(error instanceof Error ? error : new Error('The map failed to load.'))
		}
		map.on('error', (event) => fail(event.error))
		map.once('load', () => {
			try {
				prepare()
			} catch (error) {
				fail(error)
				return
			}
			map.once('idle', () => {
				clearTimeout(timer)
				resolve()
			})
		})
	})
}

function addCourse(map: MapLibreMap, line: readonly (readonly number[])[], isLoop: boolean): void {
	const fill = tokenColor('--overprint')
	const edge = tokenColor('--overprint-contrast')
	const kinds: SymbolKind[] = isLoop ? ['loop'] : ['start', 'finish']
	for (const kind of kinds) {
		map.addImage(kind, symbolImage(kind, fill, edge), { pixelRatio: PIXEL_RATIO })
	}
	const point = (kind: SymbolKind, at: readonly number[]) => ({
		type: 'Feature' as const,
		properties: { kind },
		geometry: { type: 'Point' as const, coordinates: [...at] },
	})
	const first = line[0] ?? []
	const symbols = isLoop
		? [point('loop', first)]
		: [point('finish', line.at(-1) ?? first), point('start', first)]

	map.addSource('course', {
		type: 'geojson',
		data: {
			type: 'Feature',
			properties: {},
			geometry: { type: 'LineString', coordinates: line.map((at) => [...at]) },
		},
	})
	map.addSource('course-symbols', {
		type: 'geojson',
		data: { type: 'FeatureCollection', features: symbols },
	})
	// The saved route's course style, as RouteCourse draws it.
	const round = { 'line-cap': 'round', 'line-join': 'round' } as const
	map.addLayer({
		id: 'course-casing',
		type: 'line',
		source: 'course',
		layout: round,
		paint: { 'line-color': edge, 'line-width': 8 },
	})
	map.addLayer({
		id: 'course',
		type: 'line',
		source: 'course',
		layout: round,
		paint: { 'line-color': fill, 'line-width': 5 },
	})
	map.addLayer({
		id: 'course-symbols',
		type: 'symbol',
		source: 'course-symbols',
		layout: {
			'icon-image': ['get', 'kind'],
			'icon-allow-overlap': true,
			'icon-ignore-placement': true,
			// The start on top, as on the map.
			'symbol-sort-key': ['match', ['get', 'kind'], 'start', 1, 0],
		},
	})
}

// CourseSymbol's shapes drawn into pixels, since a DOM marker would not be in the canvas.
function symbolImage(kind: SymbolKind, fill: string, edge: string): ImageData {
	const size = SYMBOL_PX * PIXEL_RATIO
	const canvas = document.createElement('canvas')
	canvas.width = size
	canvas.height = size
	const context = canvas.getContext('2d', { willReadFrequently: true })
	if (!context) throw new Error('The browser cannot draw the course symbols.')
	context.scale(size / SYMBOL_VIEW, size / SYMBOL_VIEW)
	context.fillStyle = fill
	context.strokeStyle = edge
	context.lineWidth = SYMBOL_STROKE
	context.lineJoin = 'round'
	const draw = (path: Path2D) => {
		context.fill(path)
		context.stroke(path)
	}
	const circle = (radius: number) => {
		const path = new Path2D()
		path.arc(SYMBOL_VIEW / 2, SYMBOL_VIEW / 2, radius, 0, 2 * Math.PI)
		return path
	}
	if (kind === 'start') draw(new Path2D(START_PATH))
	else if (kind === 'finish') [circle(11.5), circle(6)].forEach(draw)
	else [circle(11.5), new Path2D(LOOP_START_PATH)].forEach(draw)
	return context.getImageData(0, 0, size, size)
}

// The map with its credits on a strip over its corner, as the on-screen map shows them.
async function compose(mapCanvas: HTMLCanvasElement, frame: ImageFrame): Promise<Blob> {
	const canvas = document.createElement('canvas')
	canvas.width = frame.width * PIXEL_RATIO
	canvas.height = frame.height * PIXEL_RATIO
	const context = canvas.getContext('2d')
	if (!context) throw new Error('The browser cannot draw the image.')
	context.drawImage(mapCanvas, 0, 0, canvas.width, canvas.height)
	context.scale(PIXEL_RATIO, PIXEL_RATIO)

	const font = `${ATTRIBUTION_FONT_PX}px ${getComputedStyle(document.body).fontFamily}`
	try {
		await document.fonts.load(font, ATTRIBUTION)
	} catch {
		// The fallback font still credits the map.
	}
	context.font = font
	const strip = attributionStrip(frame, context.measureText(ATTRIBUTION).width)
	context.fillStyle = 'rgba(255, 255, 255, 0.75)'
	context.fillRect(strip.x, strip.y, strip.width, strip.height)
	context.fillStyle = 'rgba(0, 0, 0, 0.75)'
	context.textAlign = 'center'
	context.textBaseline = 'middle'
	context.fillText(ATTRIBUTION, strip.x + strip.width / 2, strip.y + strip.height / 2)

	return new Promise((resolve, reject) =>
		canvas.toBlob(
			(blob) => (blob ? resolve(blob) : reject(new Error('The image could not be made.'))),
			'image/png',
		),
	)
}
