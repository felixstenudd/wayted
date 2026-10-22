import { describe, expect, it } from 'vitest'

import {
	boundsPolygon,
	circleRing,
	clampBounds,
	distanceM,
	distanceToLineM,
	EARTH_RADIUS_M,
	ringBounds,
} from './geometry'

const stockholm = { lon: 18.0686, lat: 59.3293 }

describe('distanceM', () => {
	it('is zero between a point and itself', () => {
		expect(distanceM(stockholm, stockholm)).toBe(0)
	})

	it('measures one degree of latitude', () => {
		const oneDegreeM = (Math.PI * EARTH_RADIUS_M) / 180
		expect(distanceM({ lon: 18, lat: 59 }, { lon: 18, lat: 60 })).toBeCloseTo(oneDegreeM, 3)
	})

	it('shrinks a degree of longitude with latitude', () => {
		const atEquator = distanceM({ lon: 0, lat: 0 }, { lon: 1, lat: 0 })
		const atSixty = distanceM({ lon: 0, lat: 60 }, { lon: 1, lat: 60 })
		expect(atSixty / atEquator).toBeCloseTo(0.5, 3)
	})
})

describe('circleRing', () => {
	it('puts every point at the radius from the centre', () => {
		const ring = circleRing({ center: stockholm, radiusM: 2000 })
		for (const [lon, lat] of ring) {
			expect(distanceM(stockholm, { lon, lat })).toBeCloseTo(2000, 3)
		}
	})

	it('closes the ring', () => {
		const ring = circleRing({ center: stockholm, radiusM: 2000 }, 8)
		expect(ring).toHaveLength(9)
		expect(ring[8]).toEqual(ring[0])
	})

	it('starts due north of the centre', () => {
		const [lon, lat] = circleRing({ center: stockholm, radiusM: 2000 })[0] ?? [0, 0]
		expect(lon).toBeCloseTo(stockholm.lon, 9)
		expect(lat).toBeGreaterThan(stockholm.lat)
	})
})

describe('clampBounds', () => {
	it('leaves bounds inside the world alone', () => {
		const bounds = { west: 18, south: 59, east: 18.1, north: 59.1 }
		expect(clampBounds(bounds)).toEqual(bounds)
	})

	it('cuts a view that reaches past the edges of the world', () => {
		expect(clampBounds({ west: -200, south: -89, east: 190, north: 89 })).toEqual({
			west: -180,
			south: -85.0511287798,
			east: 180,
			north: 85.0511287798,
		})
	})
})

describe('boundsPolygon and ringBounds', () => {
	it('turn bounds into a closed ring and back', () => {
		const bounds = { west: 18, south: 59, east: 18.1, north: 59.1 }
		const polygon = boundsPolygon(bounds)
		if (polygon.type !== 'Feature' || polygon.geometry.type !== 'Polygon') throw new Error()
		const ring = polygon.geometry.coordinates[0] as [number, number][]
		expect(ring).toHaveLength(5)
		expect(ring[4]).toEqual(ring[0])
		expect(ringBounds(ring)).toEqual(bounds)
	})
})

describe('distanceToLineM', () => {
	// About 110 m of street running east.
	const street = [
		[18, 59],
		[18.002, 59],
	]

	it('measures across to the middle of the line', () => {
		const metres = distanceToLineM({ lon: 18.001, lat: 59.0001 }, street)
		expect(metres).toBeCloseTo(
			distanceM({ lon: 18.001, lat: 59 }, { lon: 18.001, lat: 59.0001 }),
			0,
		)
	})

	it('measures to the nearest end past it', () => {
		const past = { lon: 18.003, lat: 59 }
		expect(distanceToLineM(past, street)).toBeCloseTo(
			distanceM(past, { lon: 18.002, lat: 59 }),
			0,
		)
	})

	it('is zero on the line', () => {
		expect(distanceToLineM({ lon: 18.0005, lat: 59 }, street)).toBeCloseTo(0, 3)
	})
})
