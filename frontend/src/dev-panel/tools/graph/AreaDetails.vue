<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Area } from '../../dev-api/types'
import { osmUrl } from './areas'

const props = defineProps<{
	area: Area
}>()

const { t } = useI18n()

const element = computed(() =>
	t(props.area.osm_type === 'way' ? 'graph.area.way' : 'graph.area.relation', {
		id: props.area.osm_id,
	}),
)
const tags = computed(() => Object.entries(props.area.tags).sort(([a], [b]) => a.localeCompare(b)))
</script>

<template>
	<div class="flex flex-col gap-3 text-small">
		<h3 class="text-body font-semibold">{{ area.tags.name ?? element }}</h3>

		<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
			<dt class="text-graphite">{{ t('graph.area.layer') }}</dt>
			<dd>{{ area.layer }}</dd>
			<dt class="text-graphite">{{ t('graph.area.element') }}</dt>
			<dd>
				<a :href="osmUrl(area)" target="_blank" rel="noreferrer" class="underline">
					{{ element }}
				</a>
			</dd>
		</dl>

		<div>
			<h4 class="font-semibold">{{ t('graph.area.tags') }}</h4>
			<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
				<template v-for="[key, value] in tags" :key="key">
					<dt class="text-graphite">{{ key }}</dt>
					<dd class="wrap-anywhere">{{ value }}</dd>
				</template>
			</dl>
		</div>
	</div>
</template>
