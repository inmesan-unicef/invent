<template>
  <div class="DashboardProjectsBox">
    <map-solutions-box
      :active-country.sync="activeCountry"
      :active-tab.sync="activeTab"
      :active-sub-level="activeSubLevel"
      :selected-country="selectedCountry"
      :current-sub-level-projects="currentSubNationalProjects"
      :filtered-projects="filteredProjects"
      :national-projects="nationalProjects"
    />
  </div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex'

import MapSolutionsBox from './MapSolutionsBox.vue'

export default {
  components: {
    MapSolutionsBox,
  },
  props: {},
  computed: {
    ...mapGetters({
      getActiveCountry: 'search/getActiveCountry',
      selectedCountry: 'search/getSelectedCountry',
      getActiveTab: 'search/getProjectBoxActiveTab',
      activeSubLevel: 'search/getActiveSubLevel',
      currentSubNationalProjects: 'search/getSelectedCountryCurrentSubLevelSolutions',
      filteredProjects: 'search/getActiveTabSolutions',
      nationalProjects: 'search/getSelectedCountryNationalSolutions',
    }),
    activeCountry: {
      get() {
        return this.getActiveCountry
      },
      set(value) {
        this.setActiveCountry(value)
      },
    },
    activeTab: {
      get() {
        return this.getActiveTab
      },
      set(value) {
        this.setActiveTab(value)
      },
    },
  },
  methods: {
    ...mapActions({
      setActiveCountry: 'search/setActiveCountry',
      setActiveTab: 'search/setProjectBoxActiveTab',
    }),
  },
}
</script>

<style lang="less">
@import '~assets/style/variables.less';
@import '~assets/style/mixins.less';

.DashboardProjectsBox {
  .MapProjectBox {
    .el-tabs__content {
      max-height: calc(100vh - @topBarHeight - @actionBarHeight - @appFooterHeight - 156px);
      overflow-y: auto;
    }
  }
}
</style>
