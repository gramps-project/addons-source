# ----------------------------------------------------------------------------
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# ----------------------------------------------------------------------------

"""
Provides the MistralSiteFinder class, which uses Mistral AI to suggest genealogy-related
websites in JSON format.
"""

import sys
import traceback

try:
    import requests
except ImportError:
    print(
        "⚠ The 'requests' module is missing. Install it using: `pip install requests`.",
        file=sys.stderr,
    )


class MistralSiteFinder:
    """
    MistralSiteFinder class for retrieving genealogy-related websites using Mistral AI.

    This class interacts with Mistral's API to fetch a list of genealogy research websites
    while excluding certain domains and filtering results based on locale preferences.

    Attributes:
    - api_key (str): API key for Mistral authentication.

    Methods:
    - find_sites(excluded_domains, locales, include_global):
        Sends a query to Mistral and returns a JSON-formatted list of relevant genealogy websites.
    """

    def __init__(self, api_key, model):
        """
        Initialize the MistralSiteFinder with a Mistral API key.

        Args:
            api_key (str): Mistral API key used for authentication.
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

    def find_sites(self, excluded_domains, locales, include_global):
        """
        Query Mistral to find genealogy research websites.

        Args:
            excluded_domains (list of str): List of domains to exclude from results.
            locales (list of str): Regional locale codes to target.
            include_global (bool): Whether to include globally used sites.

        Returns:
            str: JSON-formatted string representing a list of sites or "[]" if an error occurs.
        """
        system_message = (
            "You assist in finding resources for genealogical research. "
            "Your response must be strictly formatted as a JSON array of objects "
            "with only two keys: 'domain' and 'url'. Do not include any additional text, "
            "explanations, or comments."
        )

        if not locales:
            locale_text = "only globally used"
            locales_str = "none"
        else:
            locale_text = (
                "both regional and globally used" if include_global else "regional"
            )
            locales_str = ", ".join(locales)

        excluded_domains_str = (
            ", ".join(excluded_domains) if excluded_domains else "none"
        )

        user_message = (
            f"I am looking for additional genealogical research websites for {locale_text} "
            f"resources. Relevant locales: {locales_str}. "
            f"Exclude the following domains: {excluded_domains_str}. "
            "Provide exactly 10 relevant websites formatted as a JSON array of objects "
            "with keys 'domain' and 'url'. "
            "Example response: [{'domain': 'example.com', 'url': 'https://example.com'}]. "
            "If no relevant websites are found, return an empty array [] without any explanations."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        }

        try:
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

        except (
            requests.ConnectionError,
            requests.ConnectTimeout,
            requests.Timeout,
            requests.ReadTimeout,
            requests.HTTPError,
            requests.TooManyRedirects,
            requests.InvalidURL,
            requests.InvalidProxyURL,
            requests.URLRequired,
            requests.MissingSchema,
            requests.InvalidSchema,
            requests.SSLError,
            requests.ProxyError,
            requests.ChunkedEncodingError,
        ) as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return "[]"

        except (
            requests.ContentDecodingError,
            requests.InvalidHeader,
            requests.StreamConsumedError,
            requests.UnrewindableBodyError,
        ) as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return "[]"

        except (
            requests.RequestsDependencyWarning,
            requests.RequestsWarning,
            requests.RetryError,
            requests.FileModeWarning,
        ) as e:
            print(f"Warning: {str(e)}")
            return "[]"

        except requests.RequestException as e:
            print(f"General request error: {str(e)}", file=sys.stderr)
            return "[]"

        except Exception as e:
            print(f"Unexpected error: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return "[]"

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(
                f"❌ Error parsing Mistral response: {e}. data: {data}", file=sys.stderr
            )
            return "[]"
