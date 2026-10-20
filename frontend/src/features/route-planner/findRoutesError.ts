import { ApiError } from '@/shared/api'

export type FindRoutesError = 'notAvailable' | 'notAccepted' | 'signedOut' | 'unexpected'

// The status codes backend/app/routing/router.py answers with.
const BY_STATUS: Partial<Record<number, FindRoutesError>> = {
	401: 'signedOut',
	422: 'notAccepted',
	501: 'notAvailable',
}

/** Which message to show for a failed route request, or null when it did not fail. */
export function findRoutesError(error: unknown): FindRoutesError | null {
	if (error === null || error === undefined) return null
	return (error instanceof ApiError && BY_STATUS[error.status]) || 'unexpected'
}
