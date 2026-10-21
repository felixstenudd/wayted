import { findRoutesError, type FindRoutesError } from './findRoutesError'
import type { FoundRoutes, Route, RouteAnswer } from './types'

// The backend answers 202 while it downloads and scores the map data around the route.
export const PREPARING_POLL_MS = 3_000
// A new area takes a minute or two, so one still waiting after five has likely stalled.
export const MAX_PREPARING_MS = 5 * 60_000

/** Where a search for a route has got to. */
export type RouteState =
	| { status: 'idle' }
	| { status: 'finding' }
	| { status: 'preparing' }
	// the best first
	| { status: 'found'; routes: Route[] }
	| { status: 'failed'; error: FindRoutesError }

/** The query for the current search, as vue-query reports it. */
export interface RouteQueryState {
	isSearching: boolean
	answer: RouteAnswer | undefined
	error: unknown
	isFetching: boolean
	// when the search started, and when its last answer came
	startedAt: number
	answeredAt: number
}

export function isFound(answer: RouteAnswer | undefined): answer is FoundRoutes {
	return answer !== undefined && 'features' in answer
}

/**
 * Whether to ask again: the map data is being prepared and has not taken too long. Judged by when
 * the answer came, so the poll and the state shown always agree.
 */
export function shouldPoll(
	answer: RouteAnswer | undefined,
	startedAt: number,
	answeredAt: number,
): boolean {
	return answer !== undefined && !isFound(answer) && answeredAt - startedAt < MAX_PREPARING_MS
}

export function routeState(query: RouteQueryState): RouteState {
	if (!query.isSearching) return { status: 'idle' }
	const error = findRoutesError(query.error)
	if (error) return { status: 'failed', error }
	if (isFound(query.answer)) return { status: 'found', routes: query.answer.features }
	if (query.answer === undefined) return { status: 'finding' }
	if (query.isFetching || shouldPoll(query.answer, query.startedAt, query.answeredAt))
		return { status: 'preparing' }
	return { status: 'failed', error: 'stillPreparing' }
}
