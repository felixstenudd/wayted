import type { components } from '@/shared/api'

export type RouteSummary = components['schemas']['RouteSummaryOut']
export type SavedRoute = components['schemas']['RouteOut']
/** A route to save: its edges and the request it was planned from. */
export type NewRoute = components['schemas']['RouteIn']
export type SavedRouteReview = components['schemas']['SavedRouteReviewOut']
export type SegmentReview = components['schemas']['SegmentReviewOut']
export type RouteReviewInput = components['schemas']['RouteReviewIn']
export type NewStretchReview = components['schemas']['SegmentReviewIn']
export type StretchReviewChange = components['schemas']['SegmentReviewChangeIn']
