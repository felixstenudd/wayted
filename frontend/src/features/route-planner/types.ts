import type { LonLat } from '@/features/map'
import type { components } from '@/shared/api'

type RouteRequestIn = components['schemas']['RouteRequestIn']

export type Activity = RouteRequestIn['activity']
export type RouteShape = RouteRequestIn['shape']
export type RouteRequest = RouteRequestIn

/** A planned route: a GeoJSON Feature, its line in travel order. */
export type Route = components['schemas']['PlannedRouteOut']
export type RouteWarning = components['schemas']['RouteWarning']
/** Why the backend found no route. */
export type NoRouteReason = components['schemas']['Reason']
/** One to three routes that go different ways, the best first: a GeoJSON FeatureCollection. */
export type FoundRoutes = components['schemas']['PlannedRoutesOut']
/** What POST /routing/routes answers: the routes, or that the map data is still being prepared. */
export type RouteAnswer = FoundRoutes | components['schemas']['PreparingOut']

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

/** Where on the route a through point goes. */
export type ThroughPointPlacement =
	{ at: 'any' } | { at: 'asap' } | { at: 'after'; afterKm: number }

/** A point the route must pass. The planner picks the order unless the placement says. */
export interface ThroughPoint {
	id: number
	lonLat: LonLat
	placement: ThroughPointPlacement
}

/** Why an edit found no way. */
export type RerouteReason = components['schemas']['RerouteReason']
/** What POST /routing/routes/reroute answers: the edited route, and where its handle goes. */
export type RerouteAnswer = components['schemas']['RerouteOut']

/** One state of an edited route: the route, and the handles where it was dragged to get there. */
export interface EditStep {
	route: Route
	handles: LonLat[]
}

/** The user's edits to one of the routes found: its steps, the route as found first. */
export interface RouteEdit {
	option: number
	steps: EditStep[]
}

/** Which point the user still has to place before routes can be found. */
export type MissingPoint = 'start' | 'finish' | null

export type StoredPreferences = components['schemas']['PreferencesOut']
