<script setup lang="ts">
import { DropdownMenuLabel } from 'reka-ui'
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = defineProps<{ class?: HTMLAttributes['class'] }>()
</script>

<template>
	<DropdownMenuLabel
		data-slot="dropdown-menu-label"
		:class="cn('px-2.5 pt-2 pb-1 text-small text-graphite', props.class)"
	>
		<slot />
	</DropdownMenuLabel>
</template>
