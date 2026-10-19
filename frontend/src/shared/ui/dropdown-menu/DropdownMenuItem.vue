<script setup lang="ts">
import { DropdownMenuItem } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = withDefaults(
	defineProps<{ disabled?: boolean; asChild?: boolean; class?: HTMLAttributes['class'] }>(),
	{ disabled: false, asChild: false, class: undefined },
)
</script>

<template>
	<!-- The highlight shows where keyboard focus is, so the focus outline is not drawn twice. -->
	<DropdownMenuItem
		data-slot="dropdown-menu-item"
		:disabled="disabled"
		:as-child="asChild"
		:class="
			cn(
				'flex h-9 cursor-default items-center gap-2.5 rounded-sm px-2.5 text-body outline-none select-none data-disabled:text-graphite data-highlighted:bg-sunken [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-graphite',
				props.class,
			)
		"
	>
		<slot />
	</DropdownMenuItem>
</template>
