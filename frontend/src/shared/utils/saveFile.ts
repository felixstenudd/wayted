const REVOKE_AFTER_MS = 30_000

/**
 * Hands a file to the browser to save, as a link with `download` would. The
 * link never enters the page, and its URL is let go once the browser has the file.
 */
export function saveFile(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob)
	const link = document.createElement('a')
	link.href = url
	link.download = filename
	link.click()
	// The browser reads the blob after the click returns, and Safari can still be starting when a
	// short wait is over, which loses the file. 30 s is what FileSaver.js waits.
	setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS)
}
