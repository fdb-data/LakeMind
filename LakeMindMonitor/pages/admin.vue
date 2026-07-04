<template>
  <div>
    <h1>Admin Monitor</h1>
    <NuxtLink to="/">← Back</NuxtLink>
    <h2>Platform Health</h2>
    <pre>{{ health }}</pre>
    <h2>Tenants</h2>
    <pre>{{ tenants }}</pre>
    <h2>Users</h2>
    <pre>{{ users }}</pre>
    <h2>Tokens</h2>
    <pre>{{ tokens }}</pre>
  </div>
</template>

<script setup>
const { data: health } = await useFetch('/api/admin/health')
const { data: tenants } = await useFetch('/api/admin/tenants')
const { data: users } = await useFetch('/api/admin/users')
const { data: tokens } = await useFetch('/api/admin/tokens')
</script>
