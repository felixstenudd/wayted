import type { VariantProps } from 'class-variance-authority'
import { cva } from 'class-variance-authority'

export { default as Button } from './Button.vue'

export const buttonVariants = cva(
	// The focus outline is left out of the transition so it appears at once in
	// its final colour instead of fading in from the text colour.
	'inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-body font-semibold whitespace-nowrap transition-[color,background-color,text-decoration-color] duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*=size-])]:size-4',
	{
		variants: {
			variant: {
				primary: 'bg-ink text-paper hover:bg-ink/85',
				secondary: 'bg-sunken text-ink hover:bg-line',
				ghost: 'text-ink hover:bg-sunken',
				link: 'text-ink underline decoration-line-strong underline-offset-3 hover:decoration-ink',
			},
			size: {
				default: 'h-10 px-4',
				sm: 'h-8 px-3 text-small font-semibold',
				lg: 'h-12 px-5',
				icon: 'size-10',
			},
		},
		compoundVariants: [{ variant: 'link', class: 'h-auto px-0' }],
		defaultVariants: {
			variant: 'primary',
			size: 'default',
		},
	},
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
