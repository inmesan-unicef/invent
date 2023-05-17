<template>
  <lazy-el-select
    slot="reference"
    v-model="innerValue"
    :placeholder="$gettext('Type and select a name') | translate"
    :remote-method="filterMethod"
    :multiple="multiple"
    filterable
    autocomplete
    remote
    clearable
    class="TeamSelector"
  >
    <el-option v-for="person in filteredOptions" :key="person.value" :label="person.label" :value="person.value">
      <span style="float: left">{{ person.label }}</span>
      <br />
      <span class="email"
        ><small>{{ person.info }}</small></span
      >
    </el-option>
  </lazy-el-select>
</template>

<script>
import { mapGetters } from 'vuex'

export default {
  $_veeValidate: {
    value() {
      return this.value
    },
    events: 'change|blur',
  },
  model: {
    prop: 'value',
    event: 'change',
  },
  props: {
    value: {
      type: Array,
      default: null,
    },
    multiple: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      filteredOptions: [],
    }
  },
  computed: {
    ...mapGetters({
      userProfiles: 'system/getUserProfilesWithLabel',
    }),
    innerValue: {
      get() {
        /**Get user ids [numArray] and translate to email array from user list, if omit email string exist we find if user id and remove it */

        return this.value.map((userId) => {
          const profile = this.userProfiles.find((profile) => profile.id === userId)
          return profile.label
        })
      },
      set(value) {
        /**Get email array as input and translate to userIds number array, If omit user exist we add it back */

        const idArray = value.map((label) => this.userProfiles.find((profile) => profile.label === label).id)

        this.$emit('change', idArray)
      },
    },
  },
  methods: {
    filterMethod(query) {
      if (query) {
        this.filteredOptions = this.userProfiles.filter(
          (p) => this.filter(p.name ? p.name : p.email, query) || (p.email ? this.filter(p.email, query) : false)
        )
      } else {
        this.filteredOptions = []
      }
    },
    filter(val, query) {
      return val.toLowerCase().startsWith(query.toLowerCase())
    },
  },
}
</script>

<style lang="less">
@import '../../assets/style/variables.less';
@import '../../assets/style/mixins.less';

.TeamSelector {
  width: 100%;
  word-wrap: normal;
  .el-select-dropdown__item.selected {
    display: none;
  }

  .el-tag {
    height: fit-content;
    word-wrap: normal;
    white-space: normal;
  }

  &.el-select {
    .el-tag {
      &:hover {
        background-color: white;
        border-color: #777779;
      }
    }
  }
}

.NoDisplay {
  display: none;
}

.TeamSelectorDropdown {
  .OrganisationItem {
    display: inline-block;
    margin-left: 6px;
    font-weight: 400;
    color: @colorGray;
    &::before {
      content: '(';
    }
    &::after {
      content: ')';
    }
  }
  li {
    height: fit-content;
    padding-bottom: 4px;
    .email {
      float: left;
      width: 100%;
      margin-top: -8px;
      line-height: 1.2;
    }
  }
}

.el-select-dropdown__item {
  max-width: 64vw;
  min-width: 740px;
  height: fit-content;
  word-wrap: normal;
  white-space: normal;
}
</style>
