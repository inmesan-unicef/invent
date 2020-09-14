from project.models import Portfolio, Project, ProjectPortfolioState, ReviewScore
from user.models import UserProfile
from project.tests.portfolio_tests import PortfolioSetup
from django.urls import reverse


class ReviewTests(PortfolioSetup):

    @staticmethod
    def get_portfolio_data(portfolio_id, client):
        url = reverse('portfolio-detailed',
                      kwargs={"pk": portfolio_id})
        return client.get(url).json()

    def setUp(self):
        super(ReviewTests, self).setUp()
        # User roles: User 1 (normal user), User 2 (global portfolio owner), User 3 (manager of portfolio 1)
        self.project = Project.objects.get(id=self.project_1_id)
        self.portfolio = Portfolio.objects.get(id=self.portfolio_id)
        # add other project
        self.project_rev_id = self.create_project("Test Project in Inventory", self.org, self.country_office,
                                                  [self.d1, self.d2], self.user_1_client)
        # Add project to portfolio
        url = reverse("portfolio-project-add", kwargs={"pk": self.portfolio_id})
        request_data = {"project": [self.project_rev_id]}
        # check permissions with user_1_client, which is not allowed
        response = self.user_1_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 403)
        # do it with user 3, who is a GPO
        response = self.user_3_client.post(url, request_data, format="json")
        # will fail because project is not in portfolio
        self.assertEqual(response.status_code, 201, response.json())
        self.assertIn(self.project_rev_id, response.json()['projects'])

        self.project_rev = Project.objects.get(id=self.project_rev_id)
        self.pps = ProjectPortfolioState.objects.get(portfolio=self.portfolio, project=self.project_rev)
        self.user_1_profile = UserProfile.objects.get(id=self.user_1_pr_id)

    def test_add_and_remove_project(self):
        project_id = self.create_project("Test Project N", self.org, self.country_office,
                                         [self.d1, self.d2], self.user_1_client)

        portfolio_data = self.get_portfolio_data(portfolio_id=self.portfolio_id, client=self.user_3_client)
        self.assertNotIn(project_id, portfolio_data['projects'])
        url = reverse('portfolio-project-add', kwargs={'pk': self.portfolio_id})
        request_data = {'project': [project_id]}
        response = self.user_3_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertIn(project_id, response.json()['projects'])
        url = reverse('portfolio-project-remove', kwargs={'pk': self.portfolio_id})
        response = self.user_3_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertNotIn(project_id, response.json()['projects'])

    def test_get_project_states(self):
        # Test 0: incorrect filter
        url = reverse("portfolio-project-list",
                      kwargs={"pk": self.portfolio_id, 'project_filter': 'wanna_ponies'})
        response = self.user_3_client.get(url, format="json")
        self.assertEqual(response.status_code, 400)
        # Test 1: inventory
        url = reverse("portfolio-project-list",
                      kwargs={"pk": self.portfolio_id, 'project_filter': 'inventory'})
        response = self.user_3_client.get(url, format="json")
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertEqual(len(resp_data), 1)
        self.assertEqual(resp_data[0]['id'], self.project_1_id)
        self.assertEqual(resp_data[0]['review_states'], None)
        # Test 2: review
        url = reverse("portfolio-project-list",
                      kwargs={"pk": self.portfolio_id, 'project_filter': 'review'})
        response = self.user_3_client.get(url, format="json")
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertEqual(len(resp_data), 1)
        self.assertEqual(resp_data[0]['id'], self.project_rev_id)
        self.assertEqual(resp_data[0]['review_states']['id'], self.pps.id)
        self.assertEqual(resp_data[0]['review_states']['review_scores'], [])  # no questionnaire sent yet
        # Test 3: complete
        url = reverse("portfolio-project-list",
                      kwargs={"pk": self.portfolio_id, 'project_filter': 'approved'})
        response = self.user_3_client.get(url, format="json")
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertEqual(len(resp_data), 0)

    def test_review_assign_questions(self):
        url = reverse("portfolio-assign-questionnaire",
                      kwargs={"portfolio_id": self.portfolio_id, 'project_id': self.project_rev.id})
        request_data = {'userprofile': [self.user_1_profile.id]}
        response = self.user_3_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        created = response.json()[0]['created']
        modified = response.json()[0]['modified']
        question_id = response.json()[0]['id']
        # Try to do it again
        response = self.user_3_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 200)
        # check that the same, unchanged object is returned
        self.assertEqual(response.json()[0]['id'], question_id)
        self.assertEqual(response.json()[0]['created'], created)
        self.assertEqual(response.json()[0]['modified'], modified)
        url = reverse('review-score-modify', kwargs={'pk': question_id})
        response = self.user_3_client.delete(url, format="json")
        self.assertEqual(response.status_code, 204)
        # check if it was removed
        questions = ReviewScore.objects.filter(id=question_id)
        self.assertEqual(len(questions), 0)

    def test_review_fill_scores(self):
        # create questions
        url = reverse("portfolio-assign-questionnaire",
                      kwargs={"portfolio_id": self.portfolio_id, 'project_id': self.project_rev_id})
        request_data = {'userprofile': [self.user_1_profile.id]}
        response = self.user_3_client.post(url, request_data, format="json")
        self.assertEqual(response.status_code, 200)

        question_id = response.json()[0]['id']
        partial_data = {
            'ee': 1,
            'ra': 5,
            'ra_text': "I don't even know what I'm doing"
        }
        url = reverse('review-score-modify', kwargs={"pk": question_id})
        response = self.user_1_client.post(url, partial_data, format="json")
        self.assertEqual(response.status_code, 200)
        url = reverse('review-score-get', kwargs={"pk": question_id})
        response = self.user_1_client.get(url, format="json")
        resp_data = response.json()
        self.assertEqual(resp_data['ee'], 1)
        self.assertEqual(resp_data['ra'], 5)
        self.assertEqual(resp_data['ra_text'], "I don't even know what I'm doing")
        faulty_data = {
            'nst': 7  # Not allowed value
        }
        url = reverse('review-score-modify', kwargs={"pk": question_id})
        response = self.user_1_client.post(url, faulty_data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['nst'], ['"7" is not a valid choice.'])
