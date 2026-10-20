<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Edge } from '../../dev-api/types'

const props = defineProps<{
	edge: Edge
}>()

const { t } = useI18n()

const scores = computed(() => Object.entries(props.edge.scores))
const feedback = computed(() =>
	Object.entries(props.edge.feedback)
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([activity, topics]) => ({
			activity,
			topics: Object.entries(topics).sort(([a], [b]) => a.localeCompare(b)),
		})),
)
const tags = computed(() => Object.entries(props.edge.tags).sort(([a], [b]) => a.localeCompare(b)))
const list = (activities: string[]) => activities.join(', ') || t('graph.edge.nobody')
</script>

<template>
	<div class="flex flex-col gap-3 text-small">
		<h3 class="text-body font-semibold">{{ t('graph.edge.title', { id: edge.id }) }}</h3>

		<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
			<dt class="text-graphite">{{ t('graph.edge.way') }}</dt>
			<dd>{{ edge.way_id }}</dd>
			<dt class="text-graphite">{{ t('graph.edge.from') }}</dt>
			<dd>{{ edge.source }}</dd>
			<dt class="text-graphite">{{ t('graph.edge.to') }}</dt>
			<dd>{{ edge.target }}</dd>
			<dt class="text-graphite">{{ t('graph.edge.length') }}</dt>
			<dd>{{ t('graph.edge.lengthM', { length: edge.length_m.toFixed(1) }) }}</dd>
			<dt class="text-graphite">{{ t('graph.edge.forward') }}</dt>
			<dd>{{ list(edge.forward) }}</dd>
			<dt class="text-graphite">{{ t('graph.edge.backward') }}</dt>
			<dd>{{ list(edge.backward) }}</dd>
		</dl>

		<div>
			<h4 class="font-semibold">{{ t('graph.edge.scores') }}</h4>
			<p v-if="scores.length === 0" class="text-graphite">{{ t('graph.edge.noScores') }}</p>
			<dl v-else class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
				<template v-for="[name, value] in scores" :key="name">
					<dt class="text-graphite">{{ name }}</dt>
					<dd>{{ value }}</dd>
				</template>
			</dl>
		</div>

		<div>
			<h4 class="font-semibold">{{ t('graph.edge.feedback') }}</h4>
			<p v-if="feedback.length === 0" class="text-graphite">{{ t('graph.edge.noFeedback') }}</p>
			<template v-for="{ activity, topics } in feedback" :key="activity">
				<h5 class="mt-1 text-graphite">{{ activity }}</h5>
				<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
					<template v-for="[topic, votes] in topics" :key="topic">
						<dt class="text-graphite">{{ topic }}</dt>
						<dd>{{ t('graph.edge.votes', { up: votes.up, down: votes.down }) }}</dd>
					</template>
				</dl>
			</template>
		</div>

		<div>
			<h4 class="font-semibold">{{ t('graph.edge.tags') }}</h4>
			<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
				<template v-for="[key, value] in tags" :key="key">
					<dt class="text-graphite">{{ key }}</dt>
					<dd class="wrap-anywhere">{{ value }}</dd>
				</template>
			</dl>
		</div>
	</div>
</template>
