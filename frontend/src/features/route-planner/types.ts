import type { components } from '@/shared/api'

type RouteRequestIn = components['schemas']['RouteRequestIn']

export type RouteAttribute = components['schemas']['AttributeOut']
export type AttributeGroup = RouteAttribute['group']

export type Activity = RouteRequestIn['activity']
export type RouteShape = RouteRequestIn['shape']
export type RouteRequest = RouteRequestIn

/** A planned route: a GeoJSON Feature, its line in travel order. */
export type Route = components['schemas']['PlannedRouteOut']
export type RouteWarning = components['schemas']['RouteWarning']
/** Why the backend found no route. */
export type NoRouteReason = components['schemas']['Reason']
/** What POST /routing/routes answers: the route, or that the map data is still being prepared. */
export type RouteAnswer = Route | components['schemas']['PreparingOut']

/** A press of Find routes. Each one is planned anew, even for the same request. */
export interface RouteSearch {
	id: number
	request: RouteRequest
	// Date.now() at the press
	startedAt: number
}

export interface DistanceRange {
	minKm: number
	maxKm: number
	defaultKm: number
}

/** Which point the user still has to place before routes can be found. */
export type MissingPoint = 'start' | 'finish' | null

export type StoredPreferences = components['schemas']['PreferencesOut']
