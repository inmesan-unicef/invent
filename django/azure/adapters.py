import json
import logging
import requests
from time import sleep

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from country.models import Country
from user.models import UserProfile

# Initialize the logger at the module level
logger = logging.getLogger(__name__)


class AzureUserManagement:
    def process_aad_users(self, max_users=100):
        """
        Fetches and processes Azure Active Directory (AAD) users.

        This function fetches users from AAD in batches, processes them, and then
        fetches the next batch, repeating this process until either there are no
        more users to fetch or a maximum number of users have been processed.

        Parameters
            max_users (int, optional): The maximum number of users to process. Defaults to 100.

        Raises
            requests.exceptions.RequestException: If an error occurs while making the request to fetch users.
        """
        max_users = int(max_users)
        # Set initial url for fetching users
        url = settings.AZURE_GET_USERS_URL
        # Get access token and set headers for the request
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        retry_count = 0
        page_count = 0
        processed_user_count = 0
        # Fetch and process users in batches until either there are no more users to fetch
        # or the maximum number of users to process has been reached
        while url and retry_count < 5 and processed_user_count < max_users:
            try:
                # Make request to fetch users
                response = requests.get(url, headers=headers)
                # Raise exception if status code is not 200
                response.raise_for_status()
                # Parse response data
                response_data = response.json()
                # Extract users from response data
                users_batch = response_data.get('value', [])
                logger.info(
                    f'Fetched {len(users_batch)} users in page {page_count+1}')
                processed_user_count += len(users_batch)

                # Process the batch of users right after fetching
                self.save_aad_users(users_batch)

                url = response_data.get('@odata.nextLink', None)
                page_count += 1
                retry_count = 0
                # TODO: Remove until further notice. If we stumple upon denial errors we can reinstate.
                # sleep(10)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error while making request to {url}: {e}")
                retry_count += 1
                # TODO: Refactor. We need to have a fallback measurement in case Azure blocks the request
                sleep(2 * (2 ** retry_count))
        logger.info(
            f'Finished processing users. Total users processed: {processed_user_count}')

    def save_aad_users(self, azure_users):
        """
        This method updates the application's user database with information fetched from Azure AD.
        It processes the users in batches to increase efficiency and reduce potential for errors or timeouts.

        It separates out new users and existing users to handle them differently, creating new user entries for new users 
        and updating existing entries for existing users. It uses Django's `bulk_create` and `bulk_update` methods 
        to perform these operations more efficiently.

        The whole process for each batch is wrapped in a database transaction to ensure data integrity. 
        If any part of the process fails, the transaction will be rolled back to the state it was in before the transaction started.

        Parameters:
            azure_users (list): A list of dictionaries where each dictionary represents a user fetched from Azure AD. 
            Each dictionary contains user attributes like email, name, job title, department, country, etc.

        Returns:
        list: A list of UserProfile objects that were updated or created in the process.
        """
        # Log the total number of users to be processed
        logger.info(f"Total Azure users to be processed: {len(azure_users)}")

        # Get the User model
        user_model = get_user_model()
        # Set the number of users to process in each batch
        batch_size = 100
        # Initialize a list to hold the users that have been updated
        updated_users = []

        # Process the users in batches
        for i in range(0, len(azure_users), batch_size):
            # Create a batch of users to process
            batch = azure_users[i:i + batch_size]
            logger.info(f"Processing batch starting at index: {i}")
            # Initialize lists to hold data for new and existing users
            new_users_data = []
            existing_users_data = []
            batch_social_account_uids = [
                user.get('id') or '' for user in batch]
            existing_social_account_uids = set(
                SocialAccount.objects.filter(uid__in=batch_social_account_uids).values_list('uid', flat=True))

            # Separate the users in the batch into new and existing users
            for azure_user in batch:
                # Create a dictionary to hold the user's data
                user_data = {
                    'email': azure_user.get('mail') or azure_user.get('userPrincipalName') or '',
                    'username': azure_user.get('mail') or azure_user.get('displayName') or azure_user.get('givenName') or azure_user.get('userPrincipalName') or '',
                    'name': azure_user.get('displayName', ''),
                    'job_title': azure_user.get('jobTitle', ''),
                    'department': azure_user.get('department', ''),
                    'country_name': azure_user.get('country', ''),
                    'social_account_uid': azure_user.get('id', ''),
                }
            # Check if the user's social account ID is already in the database
            if user_data['social_account_uid'] in existing_social_account_uids:
                existing_users_data.append(user_data)
            else:
                new_users_data.append(user_data)

            new_users = []
            user_profiles = []
            social_accounts = []
            # Create a new User, UserProfile, and SocialAccount for each new user
            for user_data in new_users_data:
                # Get or create the user's country only if 'country_name' is not None or an empty string
                try:
                    if user_data['country_name']:
                        country, _ = Country.objects.get_or_create(
                            name=user_data['country_name'])
                    else:
                        country = None
                except Exception:
                    country = None

                # Create a new User
                user = user_model(
                    email=user_data['email'], username=user_data['username'])
                user.set_unusable_password()
                new_users.append(user)

            # Save the User instances
            # TODO: This needs refactoring, it's here for debug purposes.
            try:  # catch the error here
                new_users = user_model.objects.bulk_create(new_users)
            except Exception as e:
                logger.error(f"Error while bulk creating users: {e}")
                logger.error(
                    f"Batch of users that caused the error: {new_users_data}")
                continue  # continue to the next batch

            # Create UserProfile and SocialAccount instances for each new user
            for user, user_data in zip(new_users, new_users_data):
                # Get or create the user's country only if 'country_name' is not None or an empty string
                try:
                    if user_data['country_name']:
                        country, _ = Country.objects.get_or_create(
                            name=user_data['country_name'])
                    else:
                        country = None
                except Exception:
                    country = None

                # Create a new UserProfile
                user_profiles.append(UserProfile(
                    user=user,
                    name=user_data['name'],
                    job_title=user_data['job_title'],
                    department=user_data['department'],
                    country=country,
                    account_type=UserProfile.DONOR,
                ))

                # Create a new SocialAccount
                social_accounts.append(SocialAccount(
                    user=user, provider='azure', uid=user_data['social_account_uid']))

            # Use a transaction to create the UserProfile and SocialAccount instances
            try:
                with transaction.atomic():
                    UserProfile.objects.bulk_create(
                        user_profiles, batch_size=100)
                    SocialAccount.objects.bulk_create(
                        social_accounts, batch_size=100)
            except Exception as e:
                # Log any errors that occur during the creation process
                logger.error(
                    f'Error while creating UserProfile and SocialAccount instances: {e}')

            # Initialize a list to hold the users that need to be updated
            to_be_updated = []
            existing_users = user_model.objects.filter(
                email__in=[user_data['email'] for user_data in existing_users_data])
            existing_user_profiles = UserProfile.objects.filter(
                user__in=existing_users)

            for user_data, user, user_profile in zip(existing_users_data, existing_users, existing_user_profiles):
                try:
                    if user_data['country_name']:
                        country = Country.objects.get(
                            name=user_data['country_name'])
                    else:
                        country = None
                except Country.DoesNotExist:
                    country = None

                # Only update the user's country if the following conditions are met:
                # 1. The user's current country is None and the new country is not None
                # 2. The new country is not None
                if (user_profile.country is None and country is not None) or country is not None:
                    user_profile.country = country

                # Update the other user profile details
                user_profile.name = user_data['name']
                user_profile.job_title = user_data.get('job_title', '')
                user_profile.department = user_data.get('department', '')

                # Add the updated profile to the list of profiles to be updated
                to_be_updated.append(user_profile)

            # Use a transaction to update the user profiles
            try:
                with transaction.atomic():
                    for profile in to_be_updated:
                        profile.save()
                    # Add the updated profiles to the list of all updated users
                    updated_users.extend(to_be_updated)
            except Exception as e:
                # Log any errors that occur during the update process
                logger.error(f'Error while updating users: {e}')

        # Log the total number of updated users
        logger.info(
            f"Total existing users updated: {len(updated_users)}. Total new users created: {len(new_users)}")

        # Return the list of updated users
        return updated_users

    def get_aad_users(self, max_users=100):
        """
        Retrieves Azure Active Directory (AAD) users using Microsoft's Graph API.

        This function sends GET requests to the Graph API endpoint for users, handling pagination 
        by following the '@odata.nextLink' URL included in the response until no such link is present.
        If the request fails, it retries up to 5 times with exponential backoff to handle temporary issues.

        The function requires an access token which is fetched using the `get_access_token` method. 
        The users are returned as a list of dictionaries in the format provided by the Graph API. 
        The number of users fetched is limited by the 'max_users' parameter.

        Parameters:
            max_users (int, optional): The maximum number of users to fetch. Default is 100.

        Returns:
            list: A list of dictionaries where each dictionary represents an AAD user.

        Raises:
            requests.exceptions.RequestException: If a request to the Graph API fails.
        """
        max_users = int(max_users)
        url = settings.AZURE_GET_USERS_URL
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        users = []
        retry_count = 0
        page_count = 0
        while url and retry_count < 5 and len(users) < max_users:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                response_data = response.json()
                users_batch = response_data.get('value', [])
                users.extend(users_batch)
                logger.info(
                    f'Fetched {len(users_batch)} users in page {page_count+1}')
                logger.info(f'Users batch: {users_batch}')
                if len(users) > max_users:
                    # Limit the list to 'max_users' elements
                    users = users[:max_users]
                url = response_data.get('@odata.nextLink', None)
                page_count += 1
                retry_count = 0
                sleep(10)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error while making request to {url}: {e}")
                retry_count += 1
                sleep(10 * (2 ** retry_count))
        logger.info(
            f'Finished fetching users. Total users fetched: {len(users)}')
        return users

    def get_access_token(self):
        """
        This method is used to retrieve an access token from Azure AD.

        The access token is needed to authenticate and authorize requests made to Azure AD Graph API.
        This method sends a POST request to the Azure AD OAuth2 token endpoint with necessary details like client ID,
        client secret, and resource URL.

        The access token is returned from the function if the request is successful. If the request fails,
        it logs the error and returns None.

        Returns:
            str: The access token if the request is successful. None otherwise.
        """
        # Azure AD tenant ID
        tenant_id = settings.SOCIALACCOUNT_AZURE_TENANT
        # Azure AD client ID
        client_id = settings.SOCIALACCOUNT_PROVIDERS['azure']['APP']['client_id']
        # Azure AD client secret
        client_secret = settings.SOCIALACCOUNT_PROVIDERS['azure']['APP']['secret']
        # Resource URL for which the token is needed
        resource = 'https://graph.microsoft.com'
        # Azure AD OAuth2 token endpoint URL
        url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/token'

        # Payload for the POST request
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'resource': resource
        }

        # Send a POST request to the Azure AD OAuth2 token endpoint
        response = requests.post(url, data=payload)

        # If the request is successful
        if response.status_code == 200:
            # Parse the JSON response
            json_response = response.json()
            # Extract the access token from the response
            access_token = json_response['access_token']
            # Return the access token
            return access_token
        else:
            # Log the error if the request fails
            logger.error(
                f"Failed to get access token. Status code: {response.status_code}, Response: {response.text}")
            # Return None if the request fails
            return None

    def is_auto_signup_allowed(self, request, sociallogin):
        return True

    def create_subscription(self):
        url = 'https://graph.microsoft.com/v1.0/subscriptions'
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'changeType': 'updated',
            # replace with your actual notification URL
            'notificationUrl': 'https://your-server.com/notification-endpoint',
            'resource': '/users',
            # replace with actual expiration time
            'expirationDateTime': '2024-01-01T00:00:00Z',
            'clientState': 'SecretClientState'  # replace with actual client state
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

    def process_notification(self, notification):
        """
        Process a single change notification from Microsoft Graph.

        This involves fetching the user's data from AAD and saving it in the local database.

        Parameters
            notification (dict): A dictionary representing the change notification.
        """
        # Extract the user ID from the notification
        user_id = notification['resourceData']['id']

        # Fetch the user's data from AAD and save it in the local database
        self.process_aad_user(user_id)

    def process_aad_user(self, user_id):
        """
        Fetches and processes a single user from Azure AD
        """
        base_url = settings.MICROSOFT_GRAPH_USERS_URL
        url = f"{base_url}/{user_id}"
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            # Make request to fetch user
            response = requests.get(url, headers=headers)
            # Raise exception if status code is not 200
            response.raise_for_status()
            # Parse response data
            user_data = response.json()
            # Process the user
            self.save_aad_users([user_data])
            logger.info(f"Processed user: {user_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error while making request to {url}: {e}")
