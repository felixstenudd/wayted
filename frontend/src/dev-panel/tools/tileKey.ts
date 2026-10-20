/** One square on the map; tiles of different layers share it. */
export function tileKey(tile: { z: number; x: number; y: number }): string {
	return `${tile.z}/${tile.x}/${tile.y}`
}
