<script setup lang="ts">
import { ChevronDown } from '@lucide/vue'
import { ref, useId } from 'vue'

defineProps<{
	title: string
}>()

const isOpen = ref(true)
const contentId = useId()
</script>

<template>
	<section class="border-t border-line">
		<h2>
			<button
				type="button"
				class="flex w-full items-center justify-between gap-2 px-4 py-4 text-left text-title"
				:aria-expanded="isOpen"
				:aria-controls="contentId"
				@click="isOpen = !isOpen"
			>
				{{ title }}
				<ChevronDown
					class="size-4 shrink-0 text-graphite motion-safe:transition-transform"
					:class="{ '-rotate-90': !isOpen }"
					aria-hidden="true"
				/>
			</button>
		</h2>
		<!-- Hidden, not removed: a tool keeps its state and what it draws on the map. -->
		<div v-show="isOpen" :id="contentId" class="flex flex-col gap-3 px-4 pb-4">
			<slot />
		</div>
	</section>
</template>
