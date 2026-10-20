import { ref } from 'vue'

import type { LonLat } from '@/features/map'

export type LocationError = 'denied' | 'unavailable' | 'unsupported'

// GeolocationPositionError.PERMISSION_DENIED; the class is missing outside browsers.
const PERMISSION_DENIED = 1

/** Asks the browser where the user is. */
export function useCurrentLocation() {
	const isLocating = ref(false)
	const error = ref<LocationError | null>(null)

	/** The user's position, or null with `error` set when there is none. */
	function locate(): Promise<LonLat | null> {
		error.value = null
		if (!('geolocation' in navigator)) {
			error.value = 'unsupported'
			return Promise.resolve(null)
		}
		isLocating.value = true
		return new Promise((resolve) => {
			navigator.geolocation.getCurrentPosition(
				({ coords }) => {
					isLocating.value = false
					resolve({ lon: coords.longitude, lat: coords.latitude })
				},
				({ code }) => {
					isLocating.value = false
					error.value = code === PERMISSION_DENIED ? 'denied' : 'unavailable'
					resolve(null)
				},
				{ enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
			)
		})
	}

	return { isLocating, error, locate }
}
