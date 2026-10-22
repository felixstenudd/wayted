<script setup lang="ts">
import { DropdownMenuPortal, DropdownMenuSubContent } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = withDefaults(
	defineProps<{ sideOffset?: number; class?: HTMLAttributes['class'] }>(),
	{ sideOffset: 4, class: undefined },
)
</script>

<template>
	<DropdownMenuPortal>
		<DropdownMenuSubContent
			data-slot="dropdown-menu-sub-content"
			:side-offset="sideOffset"
			:class="
				cn(
					'z-50 min-w-40 origin-(--reka-dropdown-menu-content-transform-origin) rounded-md bg-paper p-1 text-ink shadow-float',
					'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
					props.class,
				)
			"
		>
			<slot />
		</DropdownMenuSubContent>
	</DropdownMenuPortal>
</template>
