import { readonly, ref, type Ref } from 'vue'

import { onMap, useMapContext } from '../context'
import { clampBounds, type Bounds } from '../geometry'

const PADDING_PX = 48

/** The bounds of what the map shows, and a way to move it. */
export function useMapView(): {
	bounds: Readonly<Ref<Bounds | null>>
	showBounds: (bounds: Bounds) => void
} {
	const { map } = useMapContext()
	const bounds = ref<Bounds | null>(null)

	const read = () => {
		const view = map.value?.getBounds()
		if (!view) return
		bounds.value = clampBounds({
			west: view.getWest(),
			south: view.getSouth(),
			east: view.getEast(),
			north: view.getNorth(),
		})
	}

	onMap(
		(ready) => {
			read()
			ready.on('moveend', read)
		},
		(ready) => ready.off('moveend', read),
	)

	const showBounds = ({ west, south, east, north }: Bounds) => {
		map.value?.fitBounds(
			[
				[west, south],
				[east, north],
			],
			{ padding: PADDING_PX },
		)
	}

	return { bounds: readonly(bounds), showBounds }
}
