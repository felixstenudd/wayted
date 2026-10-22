<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import { DropdownMenuSubTrigger } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = withDefaults(defineProps<{ disabled?: boolean; class?: HTMLAttributes['class'] }>(), {
	disabled: false,
	class: undefined,
})
</script>

<template>
	<!-- Styled as DropdownMenuItem; an open submenu keeps its trigger highlighted. -->
	<DropdownMenuSubTrigger
		data-slot="dropdown-menu-sub-trigger"
		:disabled="disabled"
		:class="
			cn(
				'flex h-9 cursor-default items-center gap-2.5 rounded-sm px-2.5 text-body outline-none select-none data-disabled:text-graphite data-highlighted:bg-sunken data-[state=open]:bg-sunken [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-graphite',
				props.class,
			)
		"
	>
		<slot />
		<ChevronRight class="ml-auto" aria-hidden="true" />
	</DropdownMenuSubTrigger>
</template>
