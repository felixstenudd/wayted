import type {
	CircleLayerSpecification,
	FillLayerSpecification,
	GeoJSONSource,
	LineLayerSpecification,
} from 'maplibre-gl'
import { toValue, watch, type MaybeRefOrGetter } from 'vue'

import { onMap, useMapContext } from '../context'
import type { MapData } from '../geometry'

export type SourceLayer =
	| Omit<FillLayerSpecification, 'source'>
	| Omit<LineLayerSpecification, 'source'>
	| Omit<CircleLayerSpecification, 'source'>

/**
 * A GeoJSON source and the layers drawn from it. The source follows data; both are removed with
 * the caller. Layers are drawn in the order given, above everything added before.
 */
export function useMapSource(
	id: string,
	data: MaybeRefOrGetter<MapData>,
	layers: SourceLayer[],
	// the property that becomes each feature's id
	promoteId?: string,
): void {
	const { map } = useMapContext()

	onMap(
		(ready) => {
			ready.addSource(id, {
				type: 'geojson',
				data: toValue(data),
				...(promoteId && { promoteId }),
			})
			for (const layer of layers) ready.addLayer({ ...layer, source: id })
		},
		(ready) => {
			for (const layer of layers) ready.removeLayer(layer.id)
			ready.removeSource(id)
		},
	)

	watch(
		() => toValue(data),
		(next) => {
			void map.value?.getSource<GeoJSONSource>(id)?.setData(next)
		},
	)
}
