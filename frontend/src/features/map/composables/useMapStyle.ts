import type {
	CircleLayerSpecification,
	FillLayerSpecification,
	FilterSpecification,
	LineLayerSpecification,
} from 'maplibre-gl'
import { toValue, watch, type MaybeRefOrGetter } from 'vue'

import { useMapContext } from '../context'

type PaintProperties = NonNullable<FillLayerSpecification['paint']> &
	NonNullable<LineLayerSpecification['paint']> &
	NonNullable<CircleLayerSpecification['paint']>

/** Keeps a layer's filter equal to a reactive value. Call after the useMapSource of the layer. */
export function useMapFilter(
	layerId: string,
	filter: MaybeRefOrGetter<FilterSpecification | null>,
): void {
	const { map, isReady } = useMapContext()
	watch(
		[isReady, () => toValue(filter)],
		([ready, next]) => {
			if (ready && map.value?.getLayer(layerId)) map.value.setFilter(layerId, next)
		},
		{ immediate: true },
	)
}

/** Keeps one paint property of a layer equal to a reactive value. */
export function useMapPaint<Property extends keyof PaintProperties>(
	layerId: string,
	property: Property,
	value: MaybeRefOrGetter<PaintProperties[Property]>,
): void {
	const { map, isReady } = useMapContext()
	watch(
		[isReady, () => toValue(value)],
		([ready, next]) => {
			if (ready && map.value?.getLayer(layerId))
				map.value.setPaintProperty(layerId, property, next)
		},
		{ immediate: true },
	)
}
