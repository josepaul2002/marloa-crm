<template>
  <div class="min-w-0">
    <div
      class="flex min-w-0 items-center gap-1 rounded bg-surface-gray-2 focus-within:ring-1 focus-within:ring-outline-gray-4"
    >
      <select
        v-model="country"
        :aria-label="label + ' dialling code'"
        :disabled="disabled"
        class="h-7 w-[5.5rem] shrink-0 cursor-pointer rounded-l border-0 bg-transparent py-1 pl-2 pr-5 text-sm text-ink-gray-9 focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
        @change="changeCountry"
      >
        <option value="ZZ">International</option>
        <option
          v-for="option in options"
          :key="option.country"
          :value="option.country"
        >
          {{ option.label }}
        </option>
      </select>
      <input
        ref="input"
        :value="national"
        :aria-label="label"
        :aria-invalid="Boolean(error)"
        :aria-describedby="error ? errorId : undefined"
        :disabled="disabled"
        type="tel"
        inputmode="tel"
        autocomplete="tel-national"
        :placeholder="placeholder || 'Phone number'"
        class="h-7 min-w-0 flex-1 rounded-r border-0 bg-transparent px-2 py-1 text-base text-ink-gray-9 placeholder:text-ink-gray-4 focus:ring-0 disabled:opacity-50"
        @input="inputNumber($event.target.value)"
        @blur="touched = true"
      />
    </div>
    <p
      v-if="error"
      :id="errorId"
      role="alert"
      class="mt-1 text-sm text-ink-red-4"
    >
      {{ error }}
    </p>
    <p v-if="description" class="mt-1 text-sm text-ink-gray-5">
      {{ description }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref, useId, watch } from 'vue'
import {
  diallingOptions,
  phoneError,
  phoneValue,
  splitPhone,
} from '@/utils/internationalPhone'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: 'Mobile number' },
  placeholder: { type: String, default: '' },
  description: { type: String, default: '' },
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const country = ref('IN')
const national = ref('')
const touched = ref(false)
const input = ref(null)
const errorId = useId()
const options = diallingOptions()
let lastEmitted
watch(
  () => props.modelValue,
  (value) => {
    if (value === lastEmitted) return
    const state = splitPhone(value, country.value)
    country.value = state.country
    national.value = state.national
  },
  { immediate: true },
)

const error = computed(() =>
  touched.value ? phoneError(phoneValue(national.value, country.value)) : '',
)
function emitValue() {
  lastEmitted = phoneValue(national.value, country.value)
  emit('update:modelValue', lastEmitted)
}
function inputNumber(value) {
  national.value = value
  if (/^\s*(\+|00)/.test(value)) {
    const state = splitPhone(value, country.value)
    country.value = state.country
    national.value = state.national
  }
  emitValue()
}
function changeCountry() {
  if (props.disabled) return
  touched.value = false
  emitValue()
}
defineExpose({ focus: () => input.value?.focus() })
</script>
