import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'

import { instructionText, maneuverMessage, wayClassMessage, type RouteInstruction } from './turns'

const { global: i18n } = createI18n({
	legacy: false,
	locale: 'en',
	messages: {
		en: {
			savedRoutes: {
				turns: {
					maneuvers: {
						left: 'Left',
						u_turn: 'Turn around',
						roundabout: 'Roundabout, exit {exit}',
					},
					onto: {
						left: 'Left onto {road}',
						roundabout: 'Roundabout, exit {exit} onto {road}',
					},
					ways: { cycleway: 'cycleway', other: 'path' },
				},
			},
		},
	},
})
const has = (path: string) => i18n.te(path)
const text = (instruction: Partial<RouteInstruction>) =>
	instructionText(
		{
			seq: 0,
			distance_m: 1200,
			maneuver: 'left',
			exit: null,
			name: null,
			way_class: null,
			...instruction,
		},
		i18n.t,
		has,
	)

describe('wayClassMessage', () => {
	it("names a road by its class's own word, or the generic one", () => {
		expect(wayClassMessage('cycleway', has)).toBe('savedRoutes.turns.ways.cycleway')
		expect(wayClassMessage('bridleway', has)).toBe('savedRoutes.turns.ways.other')
		expect(wayClassMessage(null, has)).toBeNull()
	})
})

describe('maneuverMessage', () => {
	it('turns onto a road only when there is one to name', () => {
		expect(maneuverMessage('sharp_right', true)).toBe('savedRoutes.turns.onto.sharp_right')
		expect(maneuverMessage('sharp_right', false)).toBe(
			'savedRoutes.turns.maneuvers.sharp_right',
		)
	})

	it('never names a road for a u-turn', () => {
		expect(maneuverMessage('u_turn', true)).toBe('savedRoutes.turns.maneuvers.u_turn')
	})
})

describe('instructionText', () => {
	it('names the road by its name, else by its class', () => {
		expect(text({ name: 'Storgatan', way_class: 'residential' })).toBe('Left onto Storgatan')
		expect(text({ way_class: 'cycleway' })).toBe('Left onto cycleway')
		expect(text({ way_class: 'bridleway' })).toBe('Left onto path')
		expect(text({})).toBe('Left')
	})

	it('says which exit to take at a roundabout', () => {
		expect(text({ maneuver: 'roundabout', exit: 2, name: 'Storgatan' })).toBe(
			'Roundabout, exit 2 onto Storgatan',
		)
		expect(text({ maneuver: 'roundabout', exit: 3 })).toBe('Roundabout, exit 3')
	})

	it('turns around without a road', () => {
		expect(text({ maneuver: 'u_turn', name: 'Storgatan' })).toBe('Turn around')
	})
})
