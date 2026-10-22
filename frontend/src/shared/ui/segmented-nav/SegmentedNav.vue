<script setup lang="ts" generic="Value extends string">
import { RouterLink } from 'vue-router'

import type { SegmentedNavItem } from '.'

// Looks like SegmentedControl, but each choice is a page: links, so they open, share and go back
// like any other.
defineProps<{
	/** Names the navigation for screen readers. */
	label: string
	items: readonly SegmentedNavItem<Value>[]
	current: Value
}>()
</script>

<template>
	<nav :aria-label="label" class="flex h-10 rounded-md bg-sunken p-0.5">
		<RouterLink
			v-for="item in items"
			:key="item.value"
			:to="item.to"
			:aria-current="item.value === current ? 'page' : undefined"
			class="flex flex-1 items-center justify-center rounded-sm border border-transparent text-small whitespace-nowrap text-graphite transition-[color,background-color,border-color] duration-150 ease-out hover:text-ink aria-[current=page]:border-line-strong aria-[current=page]:bg-paper aria-[current=page]:font-semibold aria-[current=page]:text-ink"
		>
			{{ item.label }}
		</RouterLink>
	</nav>
</template>
