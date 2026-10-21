import { ApiError } from '@/shared/api'

import type { RerouteReason } from './types'

export type EditError = 'dropOffRoad' | 'unreachable' | 'signedOut' | 'tooSlow' | 'unexpected'

const BY_REASON: Record<RerouteReason, EditError> = {
	drop_off_road: 'dropOffRoad',
	unreachable: 'unreachable',
}

function isReason(detail: string | undefined): detail is RerouteReason {
	return detail !== undefined && Object.hasOwn(BY_REASON, detail)
}

/**
 * Which message to show for an edit that failed. Any other 422 means the route sent was not one
 * the backend can follow, which the user cannot fix.
 */
export function editError(error: unknown): EditError {
	if (!(error instanceof ApiError)) return 'unexpected'
	if (error.status === 422 && isReason(error.detail)) return BY_REASON[error.detail]
	if (error.status === 401) return 'signedOut'
	if (error.status === 503) return 'tooSlow'
	return 'unexpected'
}
