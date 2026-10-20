import type { Map as MapLibreMap } from 'maplibre-gl'
import {
	inject,
	onScopeDispose,
	provide,
	ref,
	shallowRef,
	watch,
	type InjectionKey,
	type Ref,
	type ShallowRef,
} from 'vue'

export interface MapContext {
	// shallow: MapLibre objects stay out of Vue's reactivity
	map: ShallowRef<MapLibreMap | null>
	// the style is loaded, so sources and layers can be added
	isReady: Ref<boolean>
	hasBaseMapFailed: Ref<boolean>
}

const mapKey: InjectionKey<MapContext> = Symbol('map')

/** Call in the component that holds both the MapView and everything that draws on it. */
export function provideMap(): void {
	provide(mapKey, { map: shallowRef(null), isReady: ref(false), hasBaseMapFailed: ref(false) })
}

export function useMapContext(): MapContext {
	const context = inject(mapKey)
	if (!context) throw new Error('provideMap() has not been called by a parent component.')
	return context
}

/** Run add when the map is ready, and remove when the caller goes away before the map does. */
export function onMap(add: (map: MapLibreMap) => void, remove: (map: MapLibreMap) => void): void {
	const { map, isReady } = useMapContext()
	watch(
		isReady,
		(ready) => {
			if (ready && map.value) add(map.value)
		},
		{ immediate: true },
	)
	onScopeDispose(() => {
		if (isReady.value && map.value) remove(map.value)
	})
}
