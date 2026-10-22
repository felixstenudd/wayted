// Imported for its effect by every module that makes a map, so the worker is set once.
import { setWorkerUrl } from 'maplibre-gl'
// Bundled by Vite: MapLibre cannot find its own worker file once it is in a bundle.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
