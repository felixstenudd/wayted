/**
 * A CSS custom property as a colour MapLibre accepts. Our tokens are oklch, which MapLibre does
 * not read, so the browser converts: one pixel is painted and read back.
 */
export function tokenColor(name: string): string {
	const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
	const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
	if (!context || !value) return '#000000'
	context.fillStyle = value
	context.fillRect(0, 0, 1, 1)
	const [red, green, blue] = context.getImageData(0, 0, 1, 1).data
	return `rgb(${red}, ${green}, ${blue})`
}
