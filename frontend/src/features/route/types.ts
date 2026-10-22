import type { components } from '@/shared/api'

export type RouteAttribute = components['schemas']['AttributeOut']
export type AttributeGroup = RouteAttribute['group']
/** How a route scores on one attribute, as planned and saved routes describe it. */
export type AttributeScore = components['schemas']['AttributeScoreOut']
