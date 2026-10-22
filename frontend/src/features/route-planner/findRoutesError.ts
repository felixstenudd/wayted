import { ApiError } from '@/shared/api'

import type { NoRouteReason } from './types'

export type NoRouteError =
	'startOffRoad' | 'waypointOffRoad' | 'finishOffRoad' | 'unreachable' | 'noLoop'
export type FindRoutesError =
	NoRouteError | 'notAccepted' | 'tooSlow' | 'stillPreparing' | 'signedOut' | 'unexpected'

// The status codes backend/app/routing/router.py answers with.
const BY_STATUS: Partial<Record<number, FindRoutesError>> = {
	401: 'signedOut',
	422: 'notAccepted',
	503: 'tooSlow',
}

// A 422 names the reason when the settings were fine but no route was found.
const BY_REASON: Record<NoRouteReason, NoRouteError> = {
	start_off_road: 'startOffRoad',
	waypoint_off_road: 'waypointOffRoad',
	finish_off_road: 'finishOffRoad',
	unreachable: 'unreachable',
	no_loop: 'noLoop',
}

function isReason(detail: string | undefined): detail is NoRouteReason {
	return detail !== undefined && Object.hasOwn(BY_REASON, detail)
}

/** Which message to show for a failed route request, or null when it did not fail. */
export function findRoutesError(error: unknown): FindRoutesError | null {
	if (error === null || error === undefined) return null
	if (!(error instanceof ApiError)) return 'unexpected'
	if (error.status === 422 && isReason(error.detail)) return BY_REASON[error.detail]
	return BY_STATUS[error.status] ?? 'unexpected'
}
