<script setup lang="ts">
import { PopoverContent, PopoverPortal } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = withDefaults(
	defineProps<{
		side?: 'top' | 'right' | 'bottom' | 'left'
		align?: 'start' | 'center' | 'end'
		sideOffset?: number
		class?: HTMLAttributes['class']
	}>(),
	{ side: 'top', align: 'center', sideOffset: 10, class: undefined },
)

// The root is a portal, so attributes such as aria-labelledby go to the content instead.
defineOptions({ inheritAttrs: false })
</script>

<template>
	<PopoverPortal>
		<!-- Repositioned every frame, so it stays on an anchor that moves with the map. -->
		<PopoverContent
			v-bind="$attrs"
			data-slot="popover-content"
			:side="side"
			:align="align"
			:side-offset="sideOffset"
			:collision-padding="16"
			update-position-strategy="always"
			:class="
				cn(
					'z-50 w-64 origin-(--reka-popover-content-transform-origin) rounded-md bg-paper p-3 text-ink shadow-float outline-none',
					'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
					props.class,
				)
			"
		>
			<slot />
		</PopoverContent>
	</PopoverPortal>
</template>
