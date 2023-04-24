const cleanState = () => ({
  allSolutionsList: {},
  allActiveSolutionsList: [],
})

export const state = () => ({
  ...cleanState(),
})

export const getters = {
  getSolutionsList: (state) => state.allSolutionsList.solutions,
  getAllActiveSolutionsList: (state) => state.allActiveSolutionsList,
  getSolutionsListWithCountries: (state) => {
    const countriesSol = state.allSolutionsList.solutions.map((solution) => ({
      ...solution,
      countries: state.allActiveSolutionsList.find((activeSolution) => activeSolution.id === solution.id).countries,
    }))

    return countriesSol
  },
}

export const actions = {
  async loadSolutionsList({ state, commit, dispatch, rootGetters }, id) {
    const response = await this.$axios.get(`/api/portfolio/${id}`)
    commit('PUT_SOLUTION_LIST', response.data)
    return response.data
  },
  async loadAllActiveSolutionsList({ commit }) {
    const response = await this.$axios.get('api/solution')
    commit('PUT_ALL_ACTIVE_SOLUTIONS_LIST', response.data)
    return response.data
  },
}

export const mutations = {
  PUT_SOLUTION_LIST: (state, data) => {
    state.allSolutionsList = data
  },
  PUT_ALL_ACTIVE_SOLUTIONS_LIST: (state, data) => {
    state.allActiveSolutionsList = data
  },
}
