#
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
#

# ----------------------------------------------------------------------------

import json
import sys

try:
    import openai
except ImportError:
    print("⚠ OpenAI module is missing. Install it using: `pip install openai`.", file=sys.stderr)

class SiteFinder:
    """
    SiteFinder class for retrieving genealogy-related websites using OpenAI.

    This class interacts with OpenAI's API to fetch a list of genealogy research websites
    while excluding certain domains and filtering results based on locale preferences.

    Key Features:
    - Uses OpenAI to generate a list of relevant genealogy research sites.
    - Accepts excluded domains and locale-based filters.
    - Returns results in strict JSON format with "domain" and "url" keys.

    Attributes:
    - api_key (str): API key for OpenAI authentication.

    Methods:
    - find_sites(excluded_domains, locales, include_global):
        Sends a query to OpenAI and returns a JSON-formatted list of relevant genealogy websites.
    """
    def __init__(self, api_key):
        self.api_key = api_key

    def find_sites(self, excluded_domains, locales, include_global):
        system_message = (
            "You assist in finding resources for genealogical research. "
            "Your response must be strictly formatted as a JSON array of objects with only two keys: 'domain' and 'url'. "
            "Do not include any additional text, explanations, or comments."
        )

        if not locales:
            locale_text = "only globally used"
            locales_str = "none"
        else:
            locale_text = "both regional and globally used" if include_global else "regional"
            locales_str = ", ".join(locales)

        excluded_domains_str = ", ".join(excluded_domains) if excluded_domains else "none"

        user_message = (
            f"I am looking for additional genealogical research websites for {locale_text} resources. "
            f"Relevant locales: {locales_str}. "
            f"Exclude the following domains: {excluded_domains_str}. "
            "Provide exactly 10 relevant websites formatted as a JSON array of objects with keys 'domain' and 'url'. "
            "Example response: [{'{\"domain\": \"example.com\", \"url\": \"https://example.com\"}'}]. "
            "If no relevant websites are found, return an empty array [] without any explanations."
        )

        try:
            client = openai.OpenAI(api_key=self.api_key)
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            )
        except Exception as e:
            print(f"❌ Unexpected error while calling OpenAI: {e}", file=sys.stderr)
            return "[]"

        try:
            return completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Error parsing OpenAI response: {e}", file=sys.stderr)
            return "[]"