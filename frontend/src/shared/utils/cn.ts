import type { ClassValue } from 'clsx'
import { clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Our theme replaces Tailwind's type scale and shadows with role names that
// tailwind-merge cannot infer. Without this, text-body and text-graphite are
// read as two conflicting colors and one of them is silently dropped.
const twMerge = extendTailwindMerge({
	extend: {
		theme: {
			text: ['caption', 'small', 'body', 'input', 'title', 'heading', 'display', 'hero'],
			shadow: ['float'],
		},
	},
})

export function cn(...inputs: ClassValue[]): string {
	return twMerge(clsx(inputs))
}
