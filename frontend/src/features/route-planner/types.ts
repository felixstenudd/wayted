import type { components } from '@/shared/api'

type RouteRequestIn = components['schemas']['RouteRequestIn']

export type RouteAttribute = components['schemas']['AttributeOut']
export type AttributeGroup = RouteAttribute['group']

export type Activity = RouteRequestIn['activity']
export type RouteShape = RouteRequestIn['shape']
export type RouteRequest = RouteRequestIn

export interface DistanceRange {
	minKm: number
	maxKm: number
	defaultKm: number
}

/** Which point the user still has to place before routes can be found. */
export type MissingPoint = 'start' | 'finish' | null

export type StoredPreferences = components['schemas']['PreferencesOut']
