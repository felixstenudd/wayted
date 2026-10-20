import { describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api'

import { MAX_PREPARING_MS, routeState, shouldPoll, type RouteQueryState } from './route'
import type { Route } from './types'

const ROUTE: Route = {
	type: 'Feature',
	geometry: {
		type: 'LineString',
		coordinates: [
			[20.26, 63.82],
			[20.3, 63.83],
		],
	},
	properties: { length_m: 2_500, scores: {}, reused_m: 0, warnings: [] },
}
const PREPARING = { status: 'preparing' } as const

const query = (state: Partial<RouteQueryState>): RouteQueryState => ({
	isSearching: true,
	answer: undefined,
	error: null,
	isFetching: false,
	startedAt: 1_000,
	answeredAt: 1_000,
	...state,
})

describe('shouldPoll', () => {
	it('asks again while the map data is prepared', () => {
		expect(shouldPoll(PREPARING, 0, MAX_PREPARING_MS - 1)).toBe(true)
	})

	it('stops once it has taken too long', () => {
		expect(shouldPoll(PREPARING, 0, MAX_PREPARING_MS)).toBe(false)
	})

	it('stops with the route, or before any answer', () => {
		expect(shouldPoll(ROUTE, 0, 0)).toBe(false)
		expect(shouldPoll(undefined, 0, 0)).toBe(false)
	})
})

describe('routeState', () => {
	it('is idle without a search', () => {
		expect(routeState(query({ isSearching: false, answer: ROUTE }))).toEqual({ status: 'idle' })
	})

	it('is finding until the first answer', () => {
		expect(routeState(query({ isFetching: true }))).toEqual({ status: 'finding' })
	})

	it('is preparing while the map data is, between asks too', () => {
		expect(routeState(query({ answer: PREPARING }))).toEqual({ status: 'preparing' })
		expect(routeState(query({ answer: PREPARING, isFetching: true }))).toEqual({
			status: 'preparing',
		})
	})

	it('has found the route the backend answered with', () => {
		expect(routeState(query({ answer: ROUTE }))).toEqual({ status: 'found', route: ROUTE })
	})

	it('has failed on an error, even after preparing', () => {
		const error = new ApiError(422, 'no_loop')

		expect(routeState(query({ answer: PREPARING, error }))).toEqual({
			status: 'failed',
			error: 'noLoop',
		})
	})

	it('has failed once preparing took too long', () => {
		expect(
			routeState(query({ answer: PREPARING, answeredAt: 1_000 + MAX_PREPARING_MS })),
		).toEqual({ status: 'failed', error: 'stillPreparing' })
	})
})
