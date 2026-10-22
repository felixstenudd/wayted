<script setup lang="ts">
// Each attribute's look on the map, like a map legend: areas as tinted
// swatches, ways as their line, and places as a point. Unknown keys get a dot.
defineProps<{ attributeKey: string }>()
</script>

<template>
	<svg viewBox="0 0 16 16" class="size-4 shrink-0" aria-hidden="true">
		<rect
			v-if="attributeKey === 'green'"
			class="park"
			x="1.5"
			y="1.5"
			width="13"
			height="13"
			rx="2"
		/>
		<rect
			v-else-if="attributeKey === 'nature'"
			class="forest"
			x="1.5"
			y="1.5"
			width="13"
			height="13"
			rx="2"
		/>
		<rect
			v-else-if="attributeKey === 'water'"
			class="water"
			x="1.5"
			y="1.5"
			width="13"
			height="13"
			rx="2"
		/>
		<template v-else-if="attributeKey === 'quiet_streets'">
			<path class="road-casing" d="M1 8h14" />
			<path class="road" d="M1 8h14" />
		</template>
		<template v-else-if="attributeKey === 'bridges'">
			<path class="road-casing" d="M1 8h14" />
			<path class="road" d="M1 8h14" />
			<path class="bridge" d="M3 4.5q5 2 10 0M3 11.5q5-2 10 0" />
		</template>
		<template v-else-if="attributeKey === 'prepared'">
			<path class="prepared-solid" d="M1.5 8h6" />
			<path class="prepared-loose" d="M11 8h3.6" />
		</template>
		<circle v-else-if="attributeKey === 'sights'" class="sight" cx="8" cy="8" r="4" />
		<circle v-else class="unknown" cx="8" cy="8" r="2.5" />
	</svg>
</template>

<style scoped>
/* The base map's tints, mixed in oklab as DESIGN.md asks. */
/* No outline: an outlined square reads as a checkbox. */
.park {
	fill: color-mix(in oklab, var(--vegetation) 30%, var(--paper));
}
.forest {
	fill: color-mix(in oklab, var(--vegetation) 60%, var(--paper));
}
.water {
	fill: color-mix(in oklab, var(--graphite) 30%, var(--paper));
}
.road-casing {
	stroke: var(--line-strong);
	stroke-width: 6;
}
.road {
	stroke: var(--paper);
	stroke-width: 4;
}
.bridge,
.prepared-solid,
.prepared-loose {
	fill: none;
	stroke: var(--graphite);
	stroke-linecap: round;
}
.bridge {
	stroke-width: 1.25;
}
/* From paved to loose: the scale the slider moves along. */
.prepared-solid {
	stroke: var(--ink);
	stroke-width: 3;
}
.prepared-loose {
	stroke-dasharray: 0.1 3.5;
	stroke-width: 2.25;
}
.sight {
	fill: var(--paper);
	stroke: var(--ink);
	stroke-width: 2;
}
.unknown {
	fill: var(--graphite);
}
</style>
