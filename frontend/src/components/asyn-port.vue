<template>
  <h4>Asyn port: {{asyn_port.name}}</h4>
  <dictionary-table
    :dict="asyn_port"
    :cls="'asyn_port'"
    :skip_keys="['motors']">
  </dictionary-table>
  <template v-if="asyn_port.hasOwnProperty('motors')">
    <template v-for="(motor, motorname) in asyn_port.motors" :key='motorname'>
      <h5>Motor port: {{motorname}}</h5>
      <dictionary-table
        :dict="motor"
        :cls="'motor'"
        :skip_keys="[]">
      </dictionary-table>
    </template>
  </template>
</template>

<script>
export default {
  name: 'AsynPort',
  props: {
    asyn_port: Object
  }
}
</script>

<style scoped>
</style>
