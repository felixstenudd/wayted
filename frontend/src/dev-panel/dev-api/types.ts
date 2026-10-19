import type { components } from './schema'

type Schemas = components['schemas']

// openapi-fetch hands coordinate pairs back as number[], so the aliases say the same.
type Loose<Value> = Value extends readonly (infer Item)[]
	? Loose<Item>[]
	: Value extends object
		? { [Key in keyof Value]: Loose<Value[Key]> }
		: Value

export type FetchedTiles = Loose<Schemas['FeatureCollection_Polygon_FetchedTileOut_']>
export type FetchedTile = Schemas['FetchedTileOut']
export type QueuedTiles = Loose<Schemas['FeatureCollection_Polygon_QueuedTileOut_']>
export type QueuedTile = Schemas['QueuedTileOut']
export type QueueStatus = Schemas['Status']
export type Graph = Loose<Schemas['GraphOut']>
export type Edge = Schemas['EdgeOut']
export type Areas = Loose<Schemas['FeatureCollection_MultiPolygon_AreaOut_']>
export type Area = Schemas['AreaOut']
export type PendingWork = Schemas['PendingOut']
export type AreaRequest = Schemas['AreaRequestIn']
export type AreaRequestResult = Schemas['AreaRequestOut']
