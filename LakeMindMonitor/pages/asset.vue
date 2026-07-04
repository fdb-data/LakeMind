<template>
  <div>
    <h1>Asset Monitor</h1>
    <NuxtLink to="/">← Back</NuxtLink>
    <h2>Capabilities</h2>
    <pre>{{ capabilities }}</pre>
    <h2>Knowledge Bases</h2>
    <pre>{{ knowledge }}</pre>
    <h2>Skills</h2>
    <pre>{{ skills }}</pre>
    <h2>Memory</h2>
    <pre>{{ memory }}</pre>
    <h2>Ontology</h2>
    <pre>{{ ontology }}</pre>
  </div>
</template>

<script setup>
const { data: capabilities } = await useFetch('/api/asset/capabilities')
const { data: knowledge } = await useFetch('/api/asset/knowledge')
const { data: skills } = await useFetch('/api/asset/skills')
const { data: memory } = await useFetch('/api/asset/memory')
const { data: ontology } = await useFetch('/api/asset/ontology')
</script>
