<script setup lang="ts">
import { DropdownMenuContent, DropdownMenuPortal } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = withDefaults(
	defineProps<{
		align?: 'start' | 'center' | 'end'
		sideOffset?: number
		class?: HTMLAttributes['class']
	}>(),
	{ align: 'start', sideOffset: 6, class: undefined },
)
</script>

<template>
	<DropdownMenuPortal>
		<DropdownMenuContent
			data-slot="dropdown-menu-content"
			:align="align"
			:side-offset="sideOffset"
			:class="
				cn(
					'z-50 min-w-56 origin-(--reka-dropdown-menu-content-transform-origin) rounded-md bg-paper p-1 text-ink shadow-float',
					'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
					props.class,
				)
			"
		>
			<slot />
		</DropdownMenuContent>
	</DropdownMenuPortal>
</template>
